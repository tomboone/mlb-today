""" Azure Storage service """
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

import src.mlb_today.config as config

STORAGE_CONNECTION_STRING = config.STORAGE_CONNECTION_STRING
BLOB_CONTAINER_NAME = config.BLOB_CONTAINER_NAME

class StorageService:
    """ Azure Storage service """
    def __init__(self):
        self.connection_string: str = STORAGE_CONNECTION_STRING

    def save_blob(self, blob_filename: str, data: str) -> None:
        """
        Save blob to Azure Storage

        Args:
            blob_filename (str): blob file name
            data (str): data to save
        """
        blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(self.connection_string)

        container_client: ContainerClient = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container()

        blob_client: BlobClient = container_client.get_blob_client(blob_filename)
        blob_client.upload_blob(data, overwrite=True)
