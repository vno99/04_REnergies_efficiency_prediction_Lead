#This file gives the console commands to link the repo to the hugging face space

git remote add hf_REnergy https://huggingface.co/spaces/REnergies99Lead/API_REnergy_Lead
# to be modified

#initiate the repo hugging_face. 
# BEWARE: this deletes the Mandatory README.md created by Hugging face, which you will need to recreate.
# A template is given on the hf Space if missing.
## This might be avoidable by merging the two branches, but this need further investigation.
git subtree split --prefix=code/0X_API -b hf-subtree
git push hf_REnergy hf-subtree:main --force
git branch -D hf-subtree

#From then on, everything is classic except the push line
git add .
git commit -m 'your message'

git subtree push --prefix=code/0X_API hf_REnergy main

#Then, you need to push everything on the origin main as well.
git push origin main