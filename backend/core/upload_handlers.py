from django.core.files.uploadhandler import StopUpload, TemporaryFileUploadHandler


class LimitedAnswerOcrUploadHandler(TemporaryFileUploadHandler):
    """Stop writing an OCR multipart body after its route-specific byte cap."""

    def __init__(self, request, *, max_bytes: int):
        super().__init__(request)
        self.max_bytes = max_bytes
        self.received_bytes = 0

    def receive_data_chunk(self, raw_data, start):
        self.received_bytes += len(raw_data)
        if self.received_bytes > self.max_bytes:
            self.request._answer_ocr_upload_too_large = True
            raise StopUpload(connection_reset=False)
        return super().receive_data_chunk(raw_data, start)
