#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <objidl.h>
#include <shlobj.h>
#include <shldisp.h>
#include <shlwapi.h>
#include <shellapi.h>

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <cwchar>
#include <iterator>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

struct DragItem {
    const wchar_t* remote_path;
    const wchar_t* relative_path;
    std::uint64_t size;
    std::int64_t modified_unix_seconds;
    std::uint32_t is_directory;
};

namespace {

constexpr std::int32_t kDragFailed = -1;
constexpr std::int32_t kDragCancelled = 0;
constexpr std::int32_t kDragCopied = 1;
constexpr wchar_t kAdbMimeName[] = L"application/x-adb-paths";
std::mutex g_drag_operations_mutex;
std::unordered_map<std::uint64_t, std::shared_ptr<class DragOperationState>>
    g_drag_operations;
std::atomic<std::uint64_t> g_next_drag_operation{1};

class DragOperationState {
public:
    void cancel() {
        if (cancelled_.exchange(true)) {
            return;
        }
        std::lock_guard<std::mutex> guard(mutex_);
        for (HANDLE process : processes_) {
            if (process && WaitForSingleObject(process, 0) == WAIT_TIMEOUT) {
                TerminateProcess(process, ERROR_CANCELLED);
            }
        }
    }

    bool cancelled() const {
        return cancelled_.load();
    }

    void register_process(HANDLE process) {
        std::lock_guard<std::mutex> guard(mutex_);
        if (cancelled_.load()) {
            if (process && WaitForSingleObject(process, 0) == WAIT_TIMEOUT) {
                TerminateProcess(process, ERROR_CANCELLED);
            }
            return;
        }
        processes_.push_back(process);
    }

    void unregister_process(HANDLE process) {
        std::lock_guard<std::mutex> guard(mutex_);
        processes_.erase(
            std::remove(processes_.begin(), processes_.end(), process),
            processes_.end());
    }

    void start_operation() {
        std::lock_guard<std::mutex> guard(mutex_);
        operation_started_ = true;
        in_operation_ = true;
    }

    void end_operation() {
        {
            std::lock_guard<std::mutex> guard(mutex_);
            in_operation_ = false;
        }
        operation_finished_.notify_all();
    }

    bool in_operation() const {
        std::lock_guard<std::mutex> guard(mutex_);
        return in_operation_;
    }

    void wait_for_operation() {
        std::unique_lock<std::mutex> guard(mutex_);
        if (!operation_started_) {
            return;
        }
        operation_finished_.wait(guard, [this] { return !in_operation_; });
    }

private:
    std::atomic_bool cancelled_{false};
    mutable std::mutex mutex_;
    std::condition_variable operation_finished_;
    std::vector<HANDLE> processes_;
    bool operation_started_ = false;
    bool in_operation_ = false;
};

std::wstring quote_windows_argument(const std::wstring& argument) {
    std::wstring quoted = L"\"";
    std::size_t backslashes = 0;
    for (wchar_t character : argument) {
        if (character == L'\\') {
            ++backslashes;
        } else if (character == L'"') {
            quoted.append(backslashes * 2 + 1, L'\\');
            quoted.push_back(L'"');
            backslashes = 0;
        } else {
            quoted.append(backslashes, L'\\');
            backslashes = 0;
            quoted.push_back(character);
        }
    }
    quoted.append(backslashes * 2, L'\\');
    quoted.push_back(L'"');
    return quoted;
}

std::wstring make_adb_command(
    const std::wstring& adb_path,
    const std::wstring& serial,
    const std::wstring& remote_path,
    bool use_su) {
    std::wstring command = quote_windows_argument(adb_path);
    command += L" -s ";
    command += quote_windows_argument(serial);
    command += L" exec-out ";
    if (use_su) {
        std::wstring quoted_path = L"'";
        for (wchar_t character : remote_path) {
            if (character == L'\'') {
                quoted_path += L"'\\''";
            } else {
                quoted_path.push_back(character);
            }
        }
        quoted_path.push_back(L'\'');
        command += quote_windows_argument(L"su");
        command += L" -c ";
        command += quote_windows_argument(L"cat -- " + quoted_path);
    } else {
        command += quote_windows_argument(L"sh");
        command += L" -c ";
        command += quote_windows_argument(L"cat -- \"$1\"");
        command += L" adb-explorer ";
        command += quote_windows_argument(remote_path);
    }
    return command;
}

HRESULT make_error(DWORD error) {
    return HRESULT_FROM_WIN32(error ? error : ERROR_GEN_FAILURE);
}

void set_error_text(wchar_t* buffer, std::uint32_t capacity, const wchar_t* text) {
    if (!buffer || capacity == 0) {
        return;
    }
    const std::size_t length = (std::min)(
        std::wcslen(text), static_cast<std::size_t>(capacity - 1));
    std::wmemcpy(buffer, text, length);
    buffer[length] = L'\0';
}

void set_hresult_text(wchar_t* buffer, std::uint32_t capacity, HRESULT result) {
    wchar_t message[256]{};
    DWORD length = FormatMessageW(
        FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr,
        static_cast<DWORD>(result),
        0,
        message,
        static_cast<DWORD>(std::size(message)),
        nullptr);
    if (length == 0) {
        std::swprintf(message, std::size(message),
                      L"Windows drag operation failed (0x%08X).",
                      static_cast<unsigned int>(result));
    } else {
        while (length > 0 && (message[length - 1] == L'\r' || message[length - 1] == L'\n')) {
            message[--length] = L'\0';
        }
    }
    set_error_text(buffer, capacity, message);
}

FILETIME to_filetime(std::int64_t unix_seconds) {
    constexpr std::uint64_t kWindowsEpochOffset = 11644473600ULL;
    if (unix_seconds < -static_cast<std::int64_t>(kWindowsEpochOffset)) {
        return {};
    }
    const auto ticks =
        (static_cast<std::uint64_t>(unix_seconds + kWindowsEpochOffset)) * 10000000ULL;
    ULARGE_INTEGER value{};
    value.QuadPart = ticks;
    return {value.LowPart, value.HighPart};
}

HRESULT create_stream(
    const std::wstring& adb_path,
    const std::wstring& serial,
    const DragItem& item,
    bool use_su,
    const std::shared_ptr<DragOperationState>& operation,
    IStream** stream);

class AdbFileStream final : public IStream {
public:
    AdbFileStream(
        std::wstring adb_path,
        std::wstring serial,
        std::wstring remote_path,
        bool use_su,
        std::uint64_t size,
        std::shared_ptr<DragOperationState> operation)
        : adb_path_(std::move(adb_path)),
          serial_(std::move(serial)),
          remote_path_(std::move(remote_path)),
          use_su_(use_su),
          size_(size),
          operation_(std::move(operation)) {
        InitializeCriticalSection(&lock_);
    }

    ~AdbFileStream() {
        close_process(true);
        DeleteCriticalSection(&lock_);
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** object) override {
        if (!object) {
            return E_POINTER;
        }
        *object = nullptr;
        if (iid == IID_IUnknown || iid == IID_IStream || iid == IID_ISequentialStream) {
            *object = static_cast<IStream*>(this);
        } else if (iid == IID_IMarshal) {
            return marshaler_ ? marshaler_->QueryInterface(iid, object) : E_NOINTERFACE;
        } else {
            return E_NOINTERFACE;
        }
        AddRef();
        return S_OK;
    }

    ULONG STDMETHODCALLTYPE AddRef() override {
        return static_cast<ULONG>(InterlockedIncrement(&references_));
    }

    ULONG STDMETHODCALLTYPE Release() override {
        const LONG remaining = InterlockedDecrement(&references_);
        if (remaining == 0) {
            delete this;
        }
        return static_cast<ULONG>(remaining);
    }

    HRESULT STDMETHODCALLTYPE Read(void* destination, ULONG requested, ULONG* bytes_read) override {
        if (bytes_read) {
            *bytes_read = 0;
        }
        if (requested != 0 && !destination) {
            return STG_E_INVALIDPOINTER;
        }
        if (requested == 0) {
            return S_OK;
        }

        EnterCriticalSection(&lock_);
        if (operation_->cancelled()) {
            LeaveCriticalSection(&lock_);
            return STG_E_REVERTED;
        }
        HRESULT result = ensure_process();
        if (FAILED(result)) {
            LeaveCriticalSection(&lock_);
            return result;
        }

        BYTE extra_byte = 0;
        const bool at_declared_end = position_ >= size_;
        DWORD read = 0;
        void* read_target = at_declared_end ? &extra_byte : destination;
        const ULONG read_limit = at_declared_end
            ? 1U
            : static_cast<ULONG>((std::min)(
                static_cast<std::uint64_t>(requested), size_ - position_));
        if (!ReadFile(stdout_read_, read_target, read_limit, &read, nullptr)) {
            const DWORD error = GetLastError();
            if (error != ERROR_BROKEN_PIPE) {
                LeaveCriticalSection(&lock_);
                return make_error(error);
            }
        }
        if (at_declared_end && read > 0) {
            LeaveCriticalSection(&lock_);
            return make_error(ERROR_FILE_INVALID);
        }
        position_ += read;
        if (bytes_read) {
            *bytes_read = read;
        }

        if (read != 0) {
            LeaveCriticalSection(&lock_);
            return S_OK;
        }

        WaitForSingleObject(process_.hProcess, INFINITE);
        DWORD exit_code = 0;
        if (!GetExitCodeProcess(process_.hProcess, &exit_code)) {
            result = make_error(GetLastError());
        } else if (position_ != size_) {
            result = make_error(ERROR_HANDLE_EOF);
        } else if (exit_code != 0) {
            result = make_error(ERROR_READ_FAULT);
        } else {
            result = S_FALSE;
        }
        close_process(false);
        LeaveCriticalSection(&lock_);
        return result;
    }

    HRESULT STDMETHODCALLTYPE Write(const void*, ULONG, ULONG*) override {
        return STG_E_ACCESSDENIED;
    }

    HRESULT STDMETHODCALLTYPE Seek(LARGE_INTEGER move, DWORD origin, ULARGE_INTEGER* new_position) override {
        EnterCriticalSection(&lock_);
        HRESULT result = S_OK;
        if (origin == STREAM_SEEK_SET && move.QuadPart == 0) {
            close_process(true);
            position_ = 0;
        } else if (origin == STREAM_SEEK_CUR && move.QuadPart == 0) {
            // The caller is only querying the current position.
        } else {
            result = STG_E_INVALIDFUNCTION;
        }
        if (SUCCEEDED(result) && new_position) {
            new_position->QuadPart = position_;
        }
        LeaveCriticalSection(&lock_);
        return result;
    }

    HRESULT STDMETHODCALLTYPE SetSize(ULARGE_INTEGER) override {
        return STG_E_ACCESSDENIED;
    }

    HRESULT STDMETHODCALLTYPE CopyTo(
        IStream*, ULARGE_INTEGER, ULARGE_INTEGER*, ULARGE_INTEGER*) override {
        return E_NOTIMPL;
    }

    HRESULT STDMETHODCALLTYPE Commit(DWORD) override {
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE Revert() override {
        return STG_E_REVERTED;
    }

    HRESULT STDMETHODCALLTYPE LockRegion(ULARGE_INTEGER, ULARGE_INTEGER, DWORD) override {
        return STG_E_INVALIDFUNCTION;
    }

    HRESULT STDMETHODCALLTYPE UnlockRegion(ULARGE_INTEGER, ULARGE_INTEGER, DWORD) override {
        return STG_E_INVALIDFUNCTION;
    }

    HRESULT STDMETHODCALLTYPE Stat(STATSTG* statistics, DWORD flags) override {
        if (!statistics) {
            return STG_E_INVALIDPOINTER;
        }
        ZeroMemory(statistics, sizeof(*statistics));
        statistics->type = STGTY_STREAM;
        statistics->cbSize.QuadPart = size_;
        statistics->grfMode = STGM_READ;
        if ((flags & STATFLAG_NONAME) == 0) {
            statistics->pwcsName = static_cast<LPOLESTR>(
                CoTaskMemAlloc(sizeof(wchar_t) * (remote_path_.size() + 1)));
            if (!statistics->pwcsName) {
                return E_OUTOFMEMORY;
            }
            std::wmemcpy(
                statistics->pwcsName,
                remote_path_.c_str(),
                remote_path_.size() + 1);
        }
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE Clone(IStream** stream) override {
        if (!stream) {
            return STG_E_INVALIDPOINTER;
        }
        return E_NOTIMPL;
    }

    HRESULT initialize_marshaler() {
        return CoCreateFreeThreadedMarshaler(
            static_cast<IStream*>(this), &marshaler_);
    }

private:
    HRESULT ensure_process() {
        if (process_.hProcess) {
            return S_OK;
        }

        SECURITY_ATTRIBUTES security{sizeof(security), nullptr, TRUE};
        HANDLE read_handle = nullptr;
        HANDLE write_handle = nullptr;
        if (!CreatePipe(&read_handle, &write_handle, &security, 0)) {
            return make_error(GetLastError());
        }
        SetHandleInformation(read_handle, HANDLE_FLAG_INHERIT, 0);

        HANDLE null_handle = CreateFileW(
            L"NUL", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (null_handle == INVALID_HANDLE_VALUE) {
            const DWORD error = GetLastError();
            CloseHandle(read_handle);
            CloseHandle(write_handle);
            return make_error(error);
        }

        STARTUPINFOW startup{};
        startup.cb = sizeof(startup);
        startup.dwFlags = STARTF_USESTDHANDLES;
        startup.hStdInput = null_handle;
        startup.hStdOutput = write_handle;
        startup.hStdError = null_handle;

        PROCESS_INFORMATION process{};
        std::wstring command = make_adb_command(
            adb_path_, serial_, remote_path_, use_su_);
        const BOOL created = CreateProcessW(
            adb_path_.c_str(),
            command.data(),
            nullptr,
            nullptr,
            TRUE,
            CREATE_NO_WINDOW,
            nullptr,
            nullptr,
            &startup,
            &process);

        CloseHandle(null_handle);
        CloseHandle(write_handle);
        if (!created) {
            const DWORD error = GetLastError();
            CloseHandle(read_handle);
            return make_error(error);
        }

        stdout_read_ = read_handle;
        process_ = process;
        operation_->register_process(process_.hProcess);
        if (operation_->cancelled()) {
            return STG_E_REVERTED;
        }
        return S_OK;
    }

    void close_process(bool terminate) {
        if (stdout_read_) {
            CloseHandle(stdout_read_);
            stdout_read_ = nullptr;
        }
        if (process_.hProcess) {
            operation_->unregister_process(process_.hProcess);
            if (terminate && WaitForSingleObject(process_.hProcess, 0) == WAIT_TIMEOUT) {
                TerminateProcess(process_.hProcess, ERROR_CANCELLED);
            }
            WaitForSingleObject(process_.hProcess, 5000);
            CloseHandle(process_.hThread);
            CloseHandle(process_.hProcess);
            ZeroMemory(&process_, sizeof(process_));
        }
    }

    volatile LONG references_ = 1;
    IUnknown* marshaler_ = nullptr;
    CRITICAL_SECTION lock_{};
    std::wstring adb_path_;
    std::wstring serial_;
    std::wstring remote_path_;
    bool use_su_ = false;
    std::uint64_t size_ = 0;
    std::uint64_t position_ = 0;
    std::shared_ptr<DragOperationState> operation_;
    HANDLE stdout_read_ = nullptr;
    PROCESS_INFORMATION process_{};
};

HRESULT create_stream(
    const std::wstring& adb_path,
    const std::wstring& serial,
    const DragItem& item,
    bool use_su,
    const std::shared_ptr<DragOperationState>& operation,
    IStream** stream) {
    AdbFileStream* result = nullptr;
    try {
        result = new (std::nothrow) AdbFileStream(
            adb_path, serial, item.remote_path, use_su, item.size, operation);
    } catch (const std::bad_alloc&) {
        return E_OUTOFMEMORY;
    } catch (...) {
        return E_FAIL;
    }
    if (!result) {
        return E_OUTOFMEMORY;
    }
    const HRESULT status = result->initialize_marshaler();
    if (FAILED(status)) {
        result->Release();
        return status;
    }
    *stream = result;
    return S_OK;
}

class DragDataObject final : public IDataObject, public IDataObjectAsyncCapability {
public:
    DragDataObject(
        std::wstring adb_path,
        std::wstring serial,
        bool use_su,
        const DragItem* items,
        std::uint32_t count,
        std::shared_ptr<DragOperationState> operation)
        : adb_path_(std::move(adb_path)),
          serial_(std::move(serial)),
          use_su_(use_su),
          operation_(std::move(operation)) {
        items_.reserve(count);
        for (std::uint32_t index = 0; index < count; ++index) {
            OwnedItem item{
                items[index].remote_path,
                items[index].relative_path,
                items[index].size,
                items[index].modified_unix_seconds,
                items[index].is_directory != 0};
            items_.push_back(std::move(item));
        }
        paths_payload_ = utf8(serial_);
        paths_payload_.push_back('\n');
        for (const auto& item : items_) {
            if (item.relative_path.find(L'\\') != std::wstring::npos) {
                continue;
            }
            paths_payload_ += utf8(item.remote_path);
            paths_payload_.push_back('\n');
        }
        descriptor_format_ = RegisterClipboardFormatW(CFSTR_FILEDESCRIPTORW);
        contents_format_ = RegisterClipboardFormatW(CFSTR_FILECONTENTS);
        adb_paths_format_ = RegisterClipboardFormatW(kAdbMimeName);
    }

    ~DragDataObject() {
        if (marshaler_) {
            marshaler_->Release();
        }
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** object) override {
        if (!object) {
            return E_POINTER;
        }
        *object = nullptr;
        if (iid == IID_IUnknown || iid == IID_IDataObject) {
            *object = static_cast<IDataObject*>(this);
        } else if (iid == IID_IDataObjectAsyncCapability) {
            *object = static_cast<IDataObjectAsyncCapability*>(this);
        } else if (iid == IID_IMarshal) {
            return marshaler_ ? marshaler_->QueryInterface(iid, object) : E_NOINTERFACE;
        } else {
            return E_NOINTERFACE;
        }
        AddRef();
        return S_OK;
    }

    bool formats_ready() const {
        return descriptor_format_ != 0 &&
            contents_format_ != 0 &&
            adb_paths_format_ != 0;
    }

    ULONG STDMETHODCALLTYPE AddRef() override {
        return static_cast<ULONG>(InterlockedIncrement(&references_));
    }

    ULONG STDMETHODCALLTYPE Release() override {
        const LONG remaining = InterlockedDecrement(&references_);
        if (remaining == 0) {
            delete this;
        }
        return static_cast<ULONG>(remaining);
    }

    HRESULT STDMETHODCALLTYPE SetAsyncMode(BOOL do_operation_async) override {
        if (InterlockedCompareExchange(&in_operation_, 0, 0) != 0) {
            return E_UNEXPECTED;
        }
        InterlockedExchange(&async_mode_, do_operation_async ? TRUE : FALSE);
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE GetAsyncMode(BOOL* is_operation_async) override {
        if (!is_operation_async) {
            return E_POINTER;
        }
        *is_operation_async = InterlockedCompareExchange(&async_mode_, 0, 0);
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE StartOperation(IBindCtx*) override {
        if (InterlockedCompareExchange(&async_mode_, 0, 0) == 0 ||
            InterlockedCompareExchange(&in_operation_, 1, 0) != 0) {
            return E_UNEXPECTED;
        }
        operation_->start_operation();
        AddRef();
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE InOperation(BOOL* in_async_operation) override {
        if (!in_async_operation) {
            return E_POINTER;
        }
        *in_async_operation = InterlockedCompareExchange(&in_operation_, 0, 0);
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE EndOperation(HRESULT, IBindCtx*, DWORD) override {
        if (InterlockedExchange(&in_operation_, 0) == 0) {
            return E_UNEXPECTED;
        }
        operation_->end_operation();
        Release();
        return S_OK;
    }

    HRESULT initialize_marshaler() {
        return CoCreateFreeThreadedMarshaler(
            static_cast<IDataObject*>(this), &marshaler_);
    }

    HRESULT STDMETHODCALLTYPE GetData(FORMATETC* format, STGMEDIUM* medium) override {
        if (!format || !medium) {
            return E_POINTER;
        }
        ZeroMemory(medium, sizeof(*medium));
        const HRESULT query = QueryGetData(format);
        if (FAILED(query)) {
            return query;
        }

        if (format->cfFormat == descriptor_format_) {
            return make_descriptors(medium);
        }
        if (format->cfFormat == adb_paths_format_) {
            return make_paths_medium(medium);
        }
        if (operation_->cancelled()) {
            return STG_E_REVERTED;
        }

        IStream* stream = nullptr;
        const HRESULT status = create_stream(
            adb_path_, serial_, items_[format->lindex].as_drag_item(),
            use_su_, operation_, &stream);
        if (FAILED(status)) {
            return status;
        }
        medium->tymed = TYMED_ISTREAM;
        medium->pstm = stream;
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE GetDataHere(FORMATETC*, STGMEDIUM*) override {
        return DATA_E_FORMATETC;
    }

    HRESULT STDMETHODCALLTYPE QueryGetData(FORMATETC* format) override {
        if (!format) {
            return E_POINTER;
        }
        if (format->dwAspect != DVASPECT_CONTENT) {
            return DV_E_DVASPECT;
        }
        if (format->cfFormat == descriptor_format_) {
            return format->lindex == -1 && (format->tymed & TYMED_HGLOBAL)
                ? S_OK : DV_E_LINDEX;
        }
        if (format->cfFormat == adb_paths_format_) {
            return format->lindex == -1 && (format->tymed & TYMED_HGLOBAL)
                ? S_OK : DV_E_LINDEX;
        }
        if (format->cfFormat == contents_format_) {
            return format->lindex >= 0 &&
                    static_cast<std::size_t>(format->lindex) < items_.size() &&
                    !items_[format->lindex].is_directory &&
                    (format->tymed & TYMED_ISTREAM)
                ? S_OK : DV_E_LINDEX;
        }
        return DV_E_FORMATETC;
    }

    HRESULT STDMETHODCALLTYPE GetCanonicalFormatEtc(FORMATETC*, FORMATETC* output) override {
        if (!output) {
            return E_POINTER;
        }
        output->ptd = nullptr;
        return DATA_S_SAMEFORMATETC;
    }

    HRESULT STDMETHODCALLTYPE SetData(FORMATETC*, STGMEDIUM*, BOOL) override {
        return E_NOTIMPL;
    }

    HRESULT STDMETHODCALLTYPE EnumFormatEtc(DWORD direction, IEnumFORMATETC** enumerator) override {
        if (!enumerator) {
            return E_POINTER;
        }
        if (direction != DATADIR_GET) {
            return E_NOTIMPL;
        }
        FORMATETC formats[] = {
            {static_cast<CLIPFORMAT>(descriptor_format_), nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL},
            {static_cast<CLIPFORMAT>(contents_format_), nullptr, DVASPECT_CONTENT, -1, TYMED_ISTREAM},
            {static_cast<CLIPFORMAT>(adb_paths_format_), nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL},
        };
        return SHCreateStdEnumFmtEtc(
            static_cast<UINT>(std::size(formats)), formats, enumerator);
    }

    HRESULT STDMETHODCALLTYPE DAdvise(
        FORMATETC*, DWORD, IAdviseSink*, DWORD*) override {
        return OLE_E_ADVISENOTSUPPORTED;
    }

    HRESULT STDMETHODCALLTYPE DUnadvise(DWORD) override {
        return OLE_E_ADVISENOTSUPPORTED;
    }

    HRESULT STDMETHODCALLTYPE EnumDAdvise(IEnumSTATDATA** enumerator) override {
        if (enumerator) {
            *enumerator = nullptr;
        }
        return OLE_E_ADVISENOTSUPPORTED;
    }

private:
    struct OwnedItem {
        std::wstring remote_path;
        std::wstring relative_path;
        std::uint64_t size;
        std::int64_t modified_unix_seconds;
        bool is_directory;

        DragItem as_drag_item() const {
            return {remote_path.c_str(), relative_path.c_str(), size,
                    modified_unix_seconds, is_directory ? 1U : 0U};
        }
    };

    static std::string utf8(const std::wstring& text) {
        if (text.empty()) {
            return {};
        }
        const int length = WideCharToMultiByte(
            CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
            static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
        if (length <= 0) {
            return {};
        }
        std::string result(static_cast<std::size_t>(length), '\0');
        WideCharToMultiByte(
            CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
            static_cast<int>(text.size()), result.data(), length, nullptr, nullptr);
        return result;
    }

    HRESULT make_descriptors(STGMEDIUM* medium) {
        if (items_.size() >
            (std::numeric_limits<SIZE_T>::max() - sizeof(UINT)) / sizeof(FILEDESCRIPTORW)) {
            return E_OUTOFMEMORY;
        }
        const SIZE_T bytes = sizeof(UINT) + items_.size() * sizeof(FILEDESCRIPTORW);
        HGLOBAL memory = GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, bytes);
        if (!memory) {
            return E_OUTOFMEMORY;
        }
        auto* group = static_cast<FILEGROUPDESCRIPTORW*>(GlobalLock(memory));
        if (!group) {
            GlobalFree(memory);
            return E_OUTOFMEMORY;
        }
        group->cItems = static_cast<UINT>(items_.size());
        for (std::size_t index = 0; index < items_.size(); ++index) {
            FILEDESCRIPTORW& descriptor = group->fgd[index];
            const auto& item = items_[index];
            if (item.relative_path.size() >= std::size(descriptor.cFileName)) {
                GlobalUnlock(memory);
                GlobalFree(memory);
                return HRESULT_FROM_WIN32(ERROR_FILENAME_EXCED_RANGE);
            }
            descriptor.dwFlags = FD_ATTRIBUTES | FD_FILESIZE | FD_WRITESTIME;
            descriptor.dwFileAttributes = item.is_directory
                ? FILE_ATTRIBUTE_DIRECTORY : FILE_ATTRIBUTE_NORMAL;
            descriptor.nFileSizeHigh = static_cast<DWORD>(item.size >> 32);
            descriptor.nFileSizeLow = static_cast<DWORD>(item.size & 0xffffffffULL);
            descriptor.ftLastWriteTime = to_filetime(item.modified_unix_seconds);
            std::wmemcpy(
                descriptor.cFileName,
                item.relative_path.c_str(),
                item.relative_path.size() + 1);
        }
        GlobalUnlock(memory);
        medium->tymed = TYMED_HGLOBAL;
        medium->hGlobal = memory;
        return S_OK;
    }

    HRESULT make_paths_medium(STGMEDIUM* medium) {
        HGLOBAL memory = GlobalAlloc(GMEM_MOVEABLE, paths_payload_.size() + 1);
        if (!memory) {
            return E_OUTOFMEMORY;
        }
        void* destination = GlobalLock(memory);
        if (!destination) {
            GlobalFree(memory);
            return E_OUTOFMEMORY;
        }
        std::memcpy(destination, paths_payload_.c_str(), paths_payload_.size() + 1);
        GlobalUnlock(memory);
        medium->tymed = TYMED_HGLOBAL;
        medium->hGlobal = memory;
        return S_OK;
    }

    volatile LONG references_ = 1;
    volatile LONG async_mode_ = TRUE;
    volatile LONG in_operation_ = FALSE;
    IUnknown* marshaler_ = nullptr;
    std::wstring adb_path_;
    std::wstring serial_;
    bool use_su_ = false;
    std::shared_ptr<DragOperationState> operation_;
    std::vector<OwnedItem> items_;
    std::string paths_payload_;
    CLIPFORMAT descriptor_format_ = 0;
    CLIPFORMAT contents_format_ = 0;
    CLIPFORMAT adb_paths_format_ = 0;
};

class DragSource final : public IDropSource {
public:
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** object) override {
        if (!object) {
            return E_POINTER;
        }
        *object = nullptr;
        if (iid == IID_IUnknown || iid == IID_IDropSource) {
            *object = static_cast<IDropSource*>(this);
            AddRef();
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    ULONG STDMETHODCALLTYPE AddRef() override {
        return static_cast<ULONG>(InterlockedIncrement(&references_));
    }

    ULONG STDMETHODCALLTYPE Release() override {
        const LONG remaining = InterlockedDecrement(&references_);
        if (remaining == 0) {
            delete this;
        }
        return static_cast<ULONG>(remaining);
    }

    HRESULT STDMETHODCALLTYPE QueryContinueDrag(BOOL escape_pressed, DWORD key_state) override {
        if (escape_pressed) {
            return DRAGDROP_S_CANCEL;
        }
        return (key_state & (MK_LBUTTON | MK_RBUTTON)) == 0
            ? DRAGDROP_S_DROP : S_OK;
    }

    HRESULT STDMETHODCALLTYPE GiveFeedback(DWORD) override {
        return DRAGDROP_S_USEDEFAULTCURSORS;
    }

private:
    volatile LONG references_ = 1;
};

}  // namespace

extern "C" __declspec(dllexport) std::int32_t start_drag(
    const wchar_t* adb_path,
    const wchar_t* serial,
    std::uint32_t use_su,
    const DragItem* items,
    std::uint32_t count,
    wchar_t* error_buffer,
    std::uint32_t error_capacity,
    std::uint64_t* async_operation_id) {
    if (error_buffer && error_capacity > 0) {
        error_buffer[0] = L'\0';
    }
    if (async_operation_id) {
        *async_operation_id = 0;
    }
    if (!adb_path || !*adb_path || !serial || !*serial || !items || count == 0 ||
        !async_operation_id) {
        set_error_text(error_buffer, error_capacity, L"Invalid ADB drag arguments.");
        return kDragFailed;
    }

    for (std::uint32_t index = 0; index < count; ++index) {
        if (!items[index].remote_path || !items[index].relative_path ||
            !*items[index].remote_path || !*items[index].relative_path) {
            set_error_text(error_buffer, error_capacity, L"An item has an empty path.");
            return kDragFailed;
        }
    }

    const HRESULT ole_status = OleInitialize(nullptr);
    if (FAILED(ole_status)) {
        set_hresult_text(error_buffer, error_capacity, ole_status);
        return kDragFailed;
    }

    DragDataObject* data = nullptr;
    DragSource* source = nullptr;
    std::shared_ptr<DragOperationState> operation;
    try {
        operation = std::make_shared<DragOperationState>();
        data = new (std::nothrow) DragDataObject(
            adb_path, serial, use_su != 0, items, count, operation);
        source = new (std::nothrow) DragSource();
    } catch (const std::bad_alloc&) {
        if (data) data->Release();
        if (source) source->Release();
        OleUninitialize();
        set_error_text(error_buffer, error_capacity, L"Not enough memory to start the drag.");
        return kDragFailed;
    } catch (...) {
        if (data) data->Release();
        if (source) source->Release();
        OleUninitialize();
        set_error_text(error_buffer, error_capacity, L"Could not prepare the Windows drag data.");
        return kDragFailed;
    }
    if (!data || !source) {
        if (data) data->Release();
        if (source) source->Release();
        OleUninitialize();
        set_error_text(error_buffer, error_capacity, L"Not enough memory to start the drag.");
        return kDragFailed;
    }
    if (data && !data->formats_ready()) {
        data->Release();
        source->Release();
        OleUninitialize();
        set_hresult_text(
            error_buffer, error_capacity, make_error(GetLastError()));
        return kDragFailed;
    }
    const HRESULT marshaler_status = data->initialize_marshaler();
    if (FAILED(marshaler_status)) {
        data->Release();
        source->Release();
        OleUninitialize();
        set_hresult_text(error_buffer, error_capacity, marshaler_status);
        return kDragFailed;
    }

    DWORD effect = DROPEFFECT_NONE;
    const HRESULT status = DoDragDrop(data, source, DROPEFFECT_COPY, &effect);
    data->Release();
    source->Release();
    OleUninitialize();

    if (status == DRAGDROP_S_CANCEL) {
        return kDragCancelled;
    }
    if (FAILED(status)) {
        set_hresult_text(error_buffer, error_capacity, status);
        return kDragFailed;
    }
    if (SUCCEEDED(status) && (effect & DROPEFFECT_COPY) &&
        operation->in_operation()) {
        const std::uint64_t operation_id =
            g_next_drag_operation.fetch_add(1);
        {
            std::lock_guard<std::mutex> guard(g_drag_operations_mutex);
            g_drag_operations.emplace(operation_id, operation);
        }
        *async_operation_id = operation_id;
    }
    return (effect & DROPEFFECT_COPY) ? kDragCopied : kDragCancelled;
}

extern "C" __declspec(dllexport) std::int32_t cancel_drag(
    std::uint64_t operation_id) {
    std::shared_ptr<DragOperationState> operation;
    {
        std::lock_guard<std::mutex> guard(g_drag_operations_mutex);
        const auto found = g_drag_operations.find(operation_id);
        if (found == g_drag_operations.end()) {
            return 0;
        }
        operation = found->second;
    }
    if (!operation->in_operation()) {
        return 0;
    }
    operation->cancel();
    return 1;
}

extern "C" __declspec(dllexport) std::int32_t wait_for_drag(
    std::uint64_t operation_id) {
    std::shared_ptr<DragOperationState> operation;
    {
        std::lock_guard<std::mutex> guard(g_drag_operations_mutex);
        const auto found = g_drag_operations.find(operation_id);
        if (found == g_drag_operations.end()) {
            return 0;
        }
        operation = found->second;
    }
    operation->wait_for_operation();
    {
        std::lock_guard<std::mutex> guard(g_drag_operations_mutex);
        const auto found = g_drag_operations.find(operation_id);
        if (found != g_drag_operations.end() && found->second == operation) {
            g_drag_operations.erase(found);
        }
    }
    return 1;
}
