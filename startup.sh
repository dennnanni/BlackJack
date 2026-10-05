docker image ls | grep ppython
if [ $? -ne 0 ]; then
    docker build -t ppython -f Dockerfile-poetry .
fi

docker compose up --build