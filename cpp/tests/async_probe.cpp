#include "../adb_drag_source.cpp"

#include <iostream>
#include <thread>

int main() {
    const HRESULT ole_status = OleInitialize(nullptr);
    if (FAILED(ole_status)) {
        std::cerr << "OleInitialize failed.\n";
        return 1;
    }

    DragItem item{L"/unused", L"unused", 0, 0, 0};
    auto operation = std::make_shared<DragOperationState>();
    auto* data = new (std::nothrow) DragDataObject(
        L"adb.exe", L"probe", false, &item, 1, operation);
    if (!data) {
        OleUninitialize();
        std::cerr << "Could not allocate the data object.\n";
        return 1;
    }

    IDataObjectAsyncCapability* async_data = nullptr;
    HRESULT status = data->QueryInterface(
        IID_IDataObjectAsyncCapability,
        reinterpret_cast<void**>(&async_data));
    if (FAILED(status)) {
        data->Release();
        OleUninitialize();
        std::cerr << "The data object does not expose async capability.\n";
        return 1;
    }

    BOOL async_mode = FALSE;
    BOOL in_operation = TRUE;
    status = async_data->GetAsyncMode(&async_mode);
    if (FAILED(status) || !async_mode) {
        async_data->Release();
        data->Release();
        OleUninitialize();
        std::cerr << "The data object did not enable async mode.\n";
        return 1;
    }

    status = async_data->InOperation(&in_operation);
    if (FAILED(status) || in_operation) {
        async_data->Release();
        data->Release();
        OleUninitialize();
        std::cerr << "The data object reported an unexpected active operation.\n";
        return 1;
    }

    status = async_data->StartOperation(nullptr);
    if (FAILED(status)) {
        async_data->Release();
        data->Release();
        OleUninitialize();
        std::cerr << "StartOperation failed.\n";
        return 1;
    }
    data->Release();

    status = async_data->InOperation(&in_operation);
    if (FAILED(status) || !in_operation) {
        async_data->Release();
        OleUninitialize();
        std::cerr << "The data object did not retain the async operation.\n";
        return 1;
    }

    status = async_data->EndOperation(S_OK, nullptr, DROPEFFECT_COPY);
    async_data->Release();
    if (FAILED(status)) {
        OleUninitialize();
        std::cerr << "EndOperation failed.\n";
        return 1;
    }

    OleUninitialize();

    auto cancelled_operation = std::make_shared<DragOperationState>();
    AdbFileStream cancelled_stream(
        L"adb.exe", L"probe", L"/unused", false, 10, cancelled_operation);
    cancelled_operation->cancel();
    char cancelled_buffer[1]{};
    ULONG cancelled_bytes = 0;
    const HRESULT cancelled_read = cancelled_stream.Read(
        cancelled_buffer, sizeof(cancelled_buffer), &cancelled_bytes);
    if (cancelled_read != STG_E_REVERTED || cancelled_bytes != 0) {
        std::cerr << "Cancelling did not stop the virtual-file stream.\n";
        return 1;
    }

    auto waited_operation = std::make_shared<DragOperationState>();
    waited_operation->start_operation();
    std::thread end_operation([waited_operation] {
        Sleep(20);
        waited_operation->end_operation();
    });
    waited_operation->wait_for_operation();
    end_operation.join();
    if (waited_operation->in_operation()) {
        std::cerr << "Waiting did not observe EndOperation.\n";
        return 1;
    }

    std::cout << "Async operation lifetime completed successfully.\n";
    return 0;
}
