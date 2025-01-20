pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key')
        REGION_CONTROLLER_IP = credentials('REGION_CONTROLLER_IP')
    }

    stages {
        stage('Clone Repository or Update on Rack Controller') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
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

        stage('Install Dependencies') {
            steps {
                script {
                    sh '''
                    sudo apt update
                    sudo apt install -y python3-pip python3-venv
                    python3 -m venv /var/lib/jenkins/workspace/WOL/venv
                    . /var/lib/jenkins/workspace/WOL/venv/bin/activate
                    pip install --upgrade pip  # Upgrade pip to latest version
                    pip install -r requirements.txt  # Install dependencies from requirements.txt
                    '''
                }
            }
        }

        stage('Run Tests on Rack Controller') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL/tests/') {
                    sh '''
                    . /var/lib/jenkins/workspace/WOL/venv/bin/activate
                    sudo chmod +x tests.py
                    python3 tests.py
                    '''
                }
            }
        }

        stage('Clean Up Dangling Images on Rack Controller') {
            steps {
                sh 'docker image prune -f'
            }
        }

        stage('Build Docker Image on Rack Controller') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
                    script {
                        def imageName = 'maas-wol-webhook'
                        echo "Checking if Docker image '${imageName}' exists..."
                        def imageExists = sh(script: "docker images -a -q ${imageName}", returnStdout: true).trim()

                        if (imageExists) {
                            echo "Docker image '${imageName}' exists. Removing it..."
                            sh "docker rmi -f ${imageName}"
                        } else {
                            echo "Docker image '${imageName}' does not exist. Proceeding to build..."
                        }
                        sh 'docker build -t maas-wol-webhook:latest .'
                    }
                }
            }
        }

        stage('Restart Container on Rack Controller') {
            steps {
                script {
                    def runningContainer = sh(script: "docker ps -a -q -f name=maas_wol_container", returnStdout: true).trim()

                    if (runningContainer) {
                        echo "Stopping and removing existing container..."
                        sh "docker stop -t 10 maas_wol_container || true"
                        sh "docker rm -f maas_wol_container || true"
                        sh "docker image prune -f"
                    } else {
                        echo "No running container found. Proceeding to start a new one."
                    }

                    echo "Checking if port 8181 is free..."
                    sh '''
                    PORT=8181
                    if netstat -tuln | grep -q ":$PORT "; then
                        echo "Port $PORT is already in use. Stopping process..."
                        fuser -k $PORT/tcp || true
                    fi
                    '''

                    withCredentials([string(credentialsId: 'maas-api-key', variable: 'MAAS_API_KEY')]) {
                        sh '''
                        export MAAS_API_KEY=$MAAS_API_KEY
                        docker run -d --network=host --env MAAS_API_KEY=$MAAS_API_KEY -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container --restart unless-stopped maas-wol-webhook:latest
                        '''
                    }
                }
            }
        }

        stage('Test Region Connection via SSH') {
            steps {
                script {
                    sshagent(['rack_server_ssh_credentials']) {
                        sh """
                        ssh -o StrictHostKeyChecking=no localadmin@${REGION_CONTROLLER_IP} '
                            set -e # Stop if anything goes wrong
                            echo Connection Successful!
                            cd /var/lib/jenkins/workspace/WOL
                            pwd
                            git config --global --add safe.directory /var/lib/jenkins/workspace/WOL
                            sudo -u jenkins git stash
                            sudo -u jenkins git pull origin main
                            docker image prune -f
                            docker rmi -f maas-wol-webhook
                            docker build -t maas-wol-webhook:latest .
                            docker stop maas_wol_container || true
                            docker rm -f maas_wol_container || true
                            export MAAS_API_KEY=$MAAS_API_KEY
                            docker run -d --network=host --env MAAS_API_KEY=$MAAS_API_KEY -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container --restart unless-stopped maas-wol-webhook:latest
                            docker image prune -f
                            '
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'Deployment completed successfully!'
        }
        failure {
            echo 'Deployment failed. Check logs for details.'
        }
    }
}