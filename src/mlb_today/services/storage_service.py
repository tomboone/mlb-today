""" Azure Storage service """
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

import src.mlb_today.config as config

STORAGE_CONNECTION_STRING: str = config.STORAGE_CONNECTION_STRING
BLOB_CONTAINER_NAME: str = config.BLOB_CONTAINER_NAME

class StorageService:
    """ Azure Storage service """
    def __init__(self):
        self.connection_string = STORAGE_CONNECTION_STRING

    def save_blob(self, blob_filename: str, data: str, blob_container_name: str = BLOB_CONTAINER_NAME) -> None:
        """
        Save blob to Azure Storage

        Args:
            blob_filename (str): blob file name
            data (str): data to save
            blob_container_name (str): blob container name (optional)
        """
        # Create a BlobServiceClient
        blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(self.connection_string)

        # Create a container client
        container_client: ContainerClient = blob_service_client.get_container_client(blob_container_name)

        if not container_client.exists():  # If container doesn't exist, create it
            container_client.create_container()

        blob_client: BlobClient = container_client.get_blob_client(blob_filename)  # Create a blob client
        blob_client.upload_blob(data, overwrite=True)  # Upload blob

    def get_blob(self, blob_filename: str) -> BlobClient:
        """
        Get blob from Azure Storage

        Args:
            blob_filename (str): blob file name

        Returns:
            BlobClient: blob client
        """
        # Create a BlobServiceClient
        blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(self.connection_string)

        # Create a container client
        container_client: ContainerClient = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

        # Create a blob client and get the blob
        blob_client: BlobClient = container_client.get_blob_client(blob_filename)

        return blob_client
