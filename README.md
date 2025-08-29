# Saberis2Jobber


activate virtual env:
venv\Scripts\activate

DOCKER BUILD and PUSH:

docker build -t saberis2jobber-app . 

docker tag saberis2jobber-app us-west1-docker.pkg.dev/gen-lang-client-0422691587/saberis2jobber-test/saberis2jobber-app

docker push us-west1-docker.pkg.dev/gen-lang-client-0422691587/saberis2jobber-test/saberis2jobber-app