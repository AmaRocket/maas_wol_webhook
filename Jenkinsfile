pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key')
        MAAS_API_URL = credentials('maas_api_ip')
        DOCKER_USER = credentials('docker-hub-username')
        DOCKER_PASS = credentials('docker-hub-password')
        DOCKER_IMAGE = credentials('docker-hub-image')
        DOCKER_SERVICE = "maas_wol_service"
        LOG_FILE = "/var/log/docker_auto_update.log"
    }

    stages {
        stage('Clone Repository') {
            steps {
                dir('/opt/GIT/WOL/') {
                    script {
                        if (fileExists('.git')) {
                            sh 'git stash || true'
                            sh 'git pull origin main'
                        } else {
                            git branch: 'main', url: 'https://github.com/AmaRocket/maas_wol_webhook.git'
                        }
                    }
                }
            }
        }

        stage('Install Dependencies and Run Tests') {
            steps {
                dir('/opt/GIT/WOL/') {
                    sh '''
                    sudo apt update
                    sudo apt install -y python3-pip python3-venv
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt

                    cd tests/
                    sudo chmod +x tests.py
                    python3 tests.py
                    '''
                }
            }
        }

        stage('Build and Push Docker Image') {
            steps {
                dir('/opt/GIT/WOL/') {
                    script {
                        sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker build --no-cache -t $DOCKER_IMAGE:latest .
                        docker push $DOCKER_IMAGE:latest
                        '''
                    }
                }
            }
        }

        stage('Update Docker Swarm Service') {
            steps {
                script {
                    sh '''
                    echo "Updating Docker Swarm service..." | tee -a $LOG_FILE
                    docker service update --force --with-registry-auth --image $DOCKER_IMAGE:latest $DOCKER_SERVICE
                    echo "Docker Swarm service updated successfully." | tee -a $LOG_FILE
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Deployment and Swarm update completed successfully!'
        }
        failure {
            echo 'Deployment failed. Check logs for details.'
        }
    }
}