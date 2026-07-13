from app import app
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from fastapi.responses import StreamingResponse
import io

import pytest
import pandas as pd
import numpy as np

client = TestClient(app)

testdata = [
    ("tests/data/rte_national.csv", "rte_national.csv", "/rte_data?deb=2020&fin=2026&type=rte_national", "Date,Heures,Nucleaire,Gaz,Charbon,Fioul,Hydraulique,Eolien,Solaire,Bioenergies", "2025-11-01"),
    ("tests/data/rte_regional.csv", "rte_regional.csv", "/rte_data?deb=2020&fin=2026&type=rte_regional", "Date,Heures,Nucleaire,Hydraulique,Eolien,Solaire,Bioenergies,Consommation,Ech__physiques", "2025-11-01"),
]

def read_csv_file(file_path):
    """Helper function to read CSV file content"""
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.parametrize("csv_file,filename,endpoint,expectedFields, expectedValue", testdata)
def test_get_rte_data(csv_file, filename, endpoint, expectedFields, expectedValue):
    
    csv_data = read_csv_file(csv_file)

    with patch('rte.rte_data') as mock_rte_data:
        mock_stream = io.BytesIO(csv_data.encode('utf-8'))
        mock_response = StreamingResponse(
            iter(lambda: mock_stream.read(1024), b""),  # simule streaming
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
        mock_rte_data.return_value = mock_response

        response = client.get(endpoint)

        assert response.status_code == 200
        assert expectedFields in response.text
        assert expectedValue in response.text

def test_predict():
    csv_data = read_csv_file('tests/data/data_compile_predi.csv')
    sample_df = pd.read_csv(io.StringIO(csv_data))
    
    with patch('pandas.read_csv') as mock_read_csv, \
        patch('mlflow.pyfunc.load_model') as mock_load_model, \
        patch('app_func.to_boto') as mock_to_boto, \
        patch('app.getNow') as mock_get_now :
        
        # Configure the data
        mock_read_csv.return_value = sample_df

        # Create a mock model
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        # Configure the mock prediction
        mock_model.predict.return_value = np.array([10.0, 20.0, 30.0])  # Mock predictions

        # Configure the boto3 mock to do nothing
        mock_to_boto.return_value = None

        # Configure the datetime mock
        mock_get_now.return_value = "2026-01-08"

        # Make the request to our endpoint
        response = client.post("/predict")

        # Verify the response
        assert response.status_code == 200

        # Parse the response JSON
        response_data = response.json()

        # Verify the response structure
        assert "Date" in response_data
        assert "TCH_solaire_pred" in response_data
        assert "Error" in response_data

        # Verify the prediction values
        assert response_data["TCH_solaire_pred"] == [10.0, 20.0, 30.0]
        assert response_data["Error"] == [0, 0, 0]
        assert len(response_data["Date"]) == 3

        # Verify the calls
        mock_read_csv.assert_called_once()
        mock_load_model.assert_called_once()
        mock_model.predict.assert_called_once()
        assert mock_to_boto.call_count == 2
        mock_get_now.assert_called_once()
