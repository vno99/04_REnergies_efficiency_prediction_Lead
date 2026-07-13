from dotenv import load_dotenv
import os

import mlflow
from mlflow import MlflowClient

## Pour le DAG après réentrainement du modèle

# Verifier que le MLFLOW_TRACKING_URI est connu (variable d environnement) sinon :
load_dotenv()
MLFLOW_TRACKING_URI = os.environ["MLFLOW_TRACKING_URI"]

# Puis TACHE 1 - récupérer le meilleur alias : get_best_alias_by_metric(challenger, production)
# recupérer l'alias "best_alias"
# Puis TACHE 2 - mettre le meilleur alias en prod : add_alias_from_alias(old_alias=best_alias, new_alias="production")


def get_best_alias_by_metric(alias1, alias2, registered_model_name = "SolarProdModel", MlflowURI = MLFLOW_TRACKING_URI, metric_name='MAE'):
    scores={}
    mlflow.set_tracking_uri(MlflowURI)
    client = MlflowClient()

    for alias in [alias1, alias2]:
        model = client.get_model_version_by_alias(name=registered_model_name, alias=alias)
        run = client.get_run(model.run_id)
        if metric_name not in run.data.metrics:
            raise ValueError(
                f"Métrique '{metric_name}' absente pour l'alias '{alias}'"
            )
        scores[alias] = run.data.metrics[metric_name]

    metric_name = metric_name.upper()
    if metric_name in ("MAE", "RMSE", "MSE"):
        best_alias = min(scores, key=scores.get)
    elif metric_name in ('R2', 'ADJUSTED_R2'):
        best_alias = max(scores, key=scores.get)
    else:
        raise ValueError(f"Choix du meilleur modèle inconnu pour la métrique : {metric_name}")

    print(f"Best alias = {best_alias}, metric: {metric_name}={scores[best_alias]}")
    return best_alias


def add_alias_from_alias(old_alias, new_alias, MlflowURI = MLFLOW_TRACKING_URI, registered_model_name="SolarProdModel"):
    client = MlflowClient()

    model = client.get_registered_model(registered_model_name)
    aliases = model.aliases
    old_alias_version = aliases[old_alias]

    client.set_registered_model_alias(registered_model_name, new_alias, old_alias_version)
    print(f"alias {new_alias} ajouté au modele {old_alias}")
    return