pipeline {
    agent { label 'lab-linux' }

    stages {
        stage('检查项目文件') {
            steps {
                sh '''
                    echo "NODE_NAME=$NODE_NAME"
                    pwd
                    git log -1 --oneline

                    test -f app.py
                    test -f Dockerfile
                    test -f requirements.txt

                    ls -l app.py Dockerfile requirements.txt
                '''
            }
        }
    }
}
