import mlflow.pyfunc

# initiate model with:
# model_full = ServingModel(model, preprocessor)

# Call to log model on mlflow
# mlflow.pyfunc.log_model("model", python_model=AutoEncoderServingModel(model, preprocessing_transform))



class ServingModel(mlflow.pyfunc.PythonModel):
    def __init__(self, model , preprocessing_transform):
        self._model = model
        self._preprocessing_transform = preprocessing_transform

    def predict(self, model_input):
        """
        Perform a transformation and predict on input of (batch, sequence, features)
        """
        for i in range(model_input.shape[0]):
            model_input[i, :] = self._preprocessing_transform(model_input[i, :])

        return self._model.predict(model_input)
    
