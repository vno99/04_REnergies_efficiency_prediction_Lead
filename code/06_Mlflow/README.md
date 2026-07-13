---
title: Mlflow
emoji: 🏃
colorFrom: red
colorTo: red
sdk: docker
pinned: false
---

To do once :
git remote add hf_mlflow https://<user>:<hugging_face_token>@huggingface.co/spaces/REnergies99/mlflow

git subtree add --prefix=code/05_Mlflow hf_mlflow main --squash

---

git add <files_to_add>

git commit -m "<message>"

git subtree push --prefix=code/05_Mlflow mlflow main

git push origin main
