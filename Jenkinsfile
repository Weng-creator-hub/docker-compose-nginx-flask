pipeline {
    agent { label 'lab-linux' }

    environment {
        IMAGE_NAME = "flask-ci:build-${env.BUILD_NUMBER}"
    }

    stages {
        stage('检查项目文件') {
            steps {
                sh '''
                    echo "NODE_NAME=$NODE_NAME"
                    git log -1 --oneline

                    test -f app.py
                    test -f Dockerfile
                    test -f requirements.txt
                '''
            }
        }

        stage('测试健康接口') {
            steps {
                sh '''
                    docker run --rm -i --entrypoint python "$IMAGE_NAME" - < ci/smoke_test.py
                '''
            }
        }




        stage('构建镜像') {
            steps {
                sh '''
                    docker build -t "$IMAGE_NAME" --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" .
                    docker image inspect "$IMAGE_NAME" --format '{{.Id}}'
                '''
            }
        }
    }
}
