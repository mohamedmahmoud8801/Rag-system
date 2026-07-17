from enum import Enum


class ResponseSignal(Enum):
    FILE_VALIDATE_SUCCESS = "file validate success"
    FILE_TYPE_NOT_SUPPORTED = "file type not supported"
    FILE_SIZE_EXCEEDED = "file size exceeded"
    FILE_UPLODAD_SUCCESS = "file upload success"
    FILE_UPLODAD_FAILED = "file upload failed"
    