pipeline {
    agent any

    environment {
        MAAS_USER = credentials('maas_user')
        REGION_CONTROLLER_IP = credentials('region-controller-ip')
        RACK_CONTROLLER_IP = credentials('rack-controller-ip')
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
                dir('/var/lib/jenkins/workspace/WOL/') {
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
                dir('/var/lib/jenkins/workspace/WOL/') {
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
                dir('/var/lib/jenkins/workspace/WOL/') {
                    script {
                        sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker build --no-cache -t $DOCKER_IMAGE:latest .
                        docker push $DOCKER_IMAGE:latest
                        echo $DOCKER_IMAGE was deployed.
                        '''
                    }
                }
            }
        }

        stage('Clean Docker images') {
            steps {
                script {
                    sh 'docker rmi $(docker images -q) -f'
                    echo "All Images was deleted"
                }
            }
        }

        stage('Verify Docker Swarm Status') {
            steps {
                script {
                    sh 'docker info | grep Swarm'
                }
            }
        }

        stage('Remove Docker Swarm Service') {
            steps {
                script {
                    sh '''
                        echo "Updating Docker Swarm service..." | tee -a $LOG_FILE
                        echo "Removing the existing Docker Swarm service..." | tee -a $LOG_FILE
                        docker service rm $DOCKER_SERVICE || true
                        echo "SWARM SERVICE $$DOCKER_SERVICE WAS DELETED..." | tee -a $LOG_FILE
                        '''
                }
            }
        }

        stage('Clean RACK_CONTROLLER images and containers via SSH') {
            steps {
                script {
                    sshagent(['rack_server_ssh_credentials']) {
                        sh """
                        ssh -o StrictHostKeyChecking=no \$MAAS_USER@\${RACK_CONTROLLER_IP} '
                            set -e # Stop if anything goes wrong
                            echo Connection Successful!
                            docker container prune -f
                            docker image prune -af
                            echo Images and containers were cleaned!
                            '
                        """
                        echo "Checking if port 8181 is free..."
                            sh '''
                            PORT=8181
                            if netstat -tuln | grep -q ":$PORT "; then
                                echo "Port $PORT is already in use. Stopping process..."
                                fuser -k $PORT/tcp || true
                            fi
                            '''
                    }
                }
            }
        }


        stage('Clean REGION_CONTROLLER images and containers via SSH') {
            steps {
                script {
                    sshagent(['region_server_ssh_credentials']) {
                        sh """
                        ssh -o StrictHostKeyChecking=no \$MAAS_USER@\${REGION_CONTROLLER_IP} '
                            set -e # Stop if anything goes wrong
                            echo Connection Successful!
                            docker container prune -f
                            docker image prune -af
                            echo Images and containers were cleaned!
                            '
                        """
                        echo "Checking if port 8181 is free..."
                            sh '''
                            PORT=8181
                            if netstat -tuln | grep -q ":$PORT "; then
                                echo "Port $PORT is already in use. Stopping process..."
                                fuser -k $PORT/tcp || true
                            fi
                            '''
                    }
                }
            }
        }

        stage('Start Docker Swarm Service') {
            steps {
                script {
                    sh '''
                        echo "Re-creating Docker Swarm service..." | tee -a $LOG_FILE
                        docker service create \
                            --name $DOCKER_SERVICE \
                            --constraint 'node.labels.role == worker' \
                            --network host \
                            -e MAAS_API_KEY=$MAAS_API_KEY \
                            -e MAAS_API_URL=$MAAS_API_URL \
                            --mount type=bind,source=/root/.ssh,target=/root/.ssh \
                            --restart-condition any \
                            --replicas 2 \
                            $DOCKER_IMAGE:latest
                        echo "Docker Swarm service recreated successfully." | tee -a $LOG_FILE
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
