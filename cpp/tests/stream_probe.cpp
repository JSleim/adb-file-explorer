#include "../adb_drag_source.cpp"

#include <iostream>
#include <stdexcept>

namespace {

std::wstring widen(const char* value) {
    const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, nullptr, 0);
    if (length == 0) {
        throw std::runtime_error("Invalid UTF-8 argument.");
    }
    std::wstring result(static_cast<std::size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, result.data(), length);
    result.pop_back();
    return result;
}

bool read_all(IStream* stream, std::uint64_t& total) {
    char buffer[64 * 1024];
    total = 0;
    while (true) {
        ULONG received = 0;
        const HRESULT result = stream->Read(buffer, sizeof(buffer), &received);
        total += received;
        if (FAILED(result)) {
            std::wcerr << L"Stream failed with HRESULT 0x" << std::hex
                       << static_cast<unsigned long>(result) << L"\n";
            return false;
        }
        if (result == S_FALSE) {
            return true;
        }
        if (received == 0) {
            std::wcerr << L"Stream returned no data without reaching EOF.\n";
            return false;
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "Usage: adb_drag_stream_probe <adb.exe> <serial> <remote-path> <expected-size>\n";
        return 2;
    }

    const auto adb_path = widen(argv[1]);
    const auto serial = widen(argv[2]);
    const auto remote_path = widen(argv[3]);
    const std::uint64_t expected_size = std::stoull(argv[4]);
    const HRESULT ole_status = OleInitialize(nullptr);
    if (FAILED(ole_status)) {
        std::cerr << "OleInitialize failed.\n";
        return 1;
    }

    DragItem item{remote_path.c_str(), L"probe", expected_size, 0, 0};
    auto operation = std::make_shared<DragOperationState>();
    auto* data_object = new (std::nothrow) DragDataObject(
        adb_path, serial, false, &item, 1, operation);
    if (!data_object) {
        OleUninitialize();
        std::cerr << "Could not allocate the data object.\n";
        return 1;
    }

    FORMATETC descriptor_format{
        static_cast<CLIPFORMAT>(RegisterClipboardFormatW(CFSTR_FILEDESCRIPTORW)),
        nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
    STGMEDIUM descriptor_medium{};
    const HRESULT descriptor_status = data_object->GetData(
        &descriptor_format, &descriptor_medium);
    if (FAILED(descriptor_status)) {
        data_object->Release();
        OleUninitialize();
        std::cerr << "Could not read the virtual-file descriptor.\n";
        return 1;
    }
    auto* descriptor_group = static_cast<FILEGROUPDESCRIPTORW*>(
        GlobalLock(descriptor_medium.hGlobal));
    const bool descriptor_valid = descriptor_group &&
        descriptor_group->cItems == 1 &&
        std::wcscmp(descriptor_group->fgd[0].cFileName, L"probe") == 0 &&
        descriptor_group->fgd[0].nFileSizeHigh ==
            static_cast<DWORD>(expected_size >> 32) &&
        descriptor_group->fgd[0].nFileSizeLow ==
            static_cast<DWORD>(expected_size & 0xffffffffULL);
    if (descriptor_group) {
        GlobalUnlock(descriptor_medium.hGlobal);
    }
    ReleaseStgMedium(&descriptor_medium);
    if (!descriptor_valid) {
        data_object->Release();
        OleUninitialize();
        std::cerr << "The virtual-file descriptor had unexpected metadata.\n";
        return 1;
    }

    FORMATETC adb_paths_format{
        static_cast<CLIPFORMAT>(RegisterClipboardFormatW(L"application/x-adb-paths")),
        nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
    STGMEDIUM adb_paths_medium{};
    const HRESULT adb_paths_status = data_object->GetData(
        &adb_paths_format, &adb_paths_medium);
    if (FAILED(adb_paths_status)) {
        data_object->Release();
        OleUninitialize();
        std::cerr << "Could not read the in-app drag format.\n";
        return 1;
    }
    const auto* adb_paths_text = static_cast<const char*>(
        GlobalLock(adb_paths_medium.hGlobal));
    const std::string expected_adb_paths =
        std::string(argv[2]) + "\n" + argv[3] + "\n";
    const bool adb_paths_valid = adb_paths_text &&
        std::string(adb_paths_text) == expected_adb_paths;
    if (adb_paths_text) {
        GlobalUnlock(adb_paths_medium.hGlobal);
    }
    ReleaseStgMedium(&adb_paths_medium);
    if (!adb_paths_valid) {
        data_object->Release();
        OleUninitialize();
        std::cerr << "The in-app drag format contained unexpected paths.\n";
        return 1;
    }

    FORMATETC contents_format{
        static_cast<CLIPFORMAT>(RegisterClipboardFormatW(CFSTR_FILECONTENTS)),
        nullptr, DVASPECT_CONTENT, 0, TYMED_ISTREAM};
    STGMEDIUM contents_medium{};
    const HRESULT open_status = data_object->GetData(
        &contents_format, &contents_medium);
    data_object->Release();
    if (FAILED(open_status)) {
        OleUninitialize();
        std::cerr << "Could not open the virtual-file stream.\n";
        return 1;
    }
    IStream* stream = contents_medium.pstm;

    char prefix[4096];
    ULONG prefix_size = 0;
    const HRESULT prefix_status = stream->Read(prefix, sizeof(prefix), &prefix_size);
    if (FAILED(prefix_status) || (expected_size > 0 && prefix_size == 0)) {
        ReleaseStgMedium(&contents_medium);
        OleUninitialize();
        std::cerr << "Could not read the beginning of the ADB stream.\n";
        return 1;
    }

    LARGE_INTEGER rewind{};
    const HRESULT seek_status = stream->Seek(rewind, STREAM_SEEK_SET, nullptr);
    if (FAILED(seek_status)) {
        ReleaseStgMedium(&contents_medium);
        OleUninitialize();
        std::cerr << "Could not rewind the ADB stream.\n";
        return 1;
    }

    char rewound_prefix[4096];
    ULONG rewound_size = 0;
    const HRESULT rewind_read_status = stream->Read(
        rewound_prefix, sizeof(rewound_prefix), &rewound_size);
    if (FAILED(rewind_read_status) || rewound_size != prefix_size ||
        std::memcmp(prefix, rewound_prefix, prefix_size) != 0) {
        ReleaseStgMedium(&contents_medium);
        OleUninitialize();
        std::cerr << "Rewinding did not reproduce the stream prefix.\n";
        return 1;
    }

    LARGE_INTEGER rewind_again{};
    const HRESULT rewind_again_status = stream->Seek(
        rewind_again, STREAM_SEEK_SET, nullptr);
    if (FAILED(rewind_again_status)) {
        ReleaseStgMedium(&contents_medium);
        OleUninitialize();
        std::cerr << "Could not rewind the stream for the full-size check.\n";
        return 1;
    }
    std::uint64_t total = 0;
    const bool read_ok = read_all(stream, total);
    ReleaseStgMedium(&contents_medium);
    OleUninitialize();

    if (!read_ok || total != expected_size) {
        std::cerr << "Read " << total << " bytes; expected " << expected_size << ".\n";
        return 1;
    }
    std::cout << "Streamed and rewound " << total << " bytes successfully.\n";
    return 0;
}
