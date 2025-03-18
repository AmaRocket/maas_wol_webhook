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

        stage('Update Docker Swarm Service') {
            steps {
                script {
                    sh '''
                        echo "Stop HAproxy"
                        sudo systemctl stop haproxy.service
                        sleep 5
                        echo "HAproxy was stopped"
                        echo "Updating Docker Swarm service..." | tee -a $LOG_FILE
                        echo "Removing the existing Docker Swarm service..." | tee -a $LOG_FILE
                        docker service rm $DOCKER_SERVICE || true
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
                            --health-cmd "curl -f http://localhost:8181/health || exit 1" \
                            --health-interval 5s \
                            --health-retries 2 \
                            --health-timeout 1s \
                            $DOCKER_IMAGE:latest
                        echo "Docker Swarm service recreated successfully." | tee -a $LOG_FILE

                        echo "Start HAproxy"
                        sudo systemctl start haproxy.service
                        echo "HAproxy was started"

                        '''
                }
            }
        }

        stage('Docker Cleanup') {
            steps {
                script {
                    sh '''
                    # Remove the docker-cleaner service if it exists
                    docker service rm docker-cleaner || true

                    # Wait for Docker to remove the service before proceeding
                    sleep 5

                    # Get the list of worker nodes and create a cleanup task on each one
                    WORKER_NODES=$(docker node ls --filter "role=worker" --format "{{.ID}}")

                    for NODE in $WORKER_NODES; do
                        echo "Creating cleanup task on worker node $NODE..."

                        # Create a cleanup service on the worker node
                        docker service create --name docker-cleaner-$NODE \
                          --mode global \
                          --node $NODE \
                          --restart-condition none \
                          --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
                          --tty docker:cli sh -c "
                            echo 'Starting Docker cleanup on worker node $NODE...';
                            docker image prune -af;
                            docker container prune -f;
                            echo 'Docker cleanup completed on worker node $NODE.'
                          "
                    done

                    # Wait for the services to finish on all worker nodes
                    while [ "$(docker service ps docker-cleaner --format '{{.CurrentState}}' | grep -c Running)" -gt 0 ]; do
                        sleep 5
                        echo 'Cleanup service still running...'
                    done

                    # Clean up by removing the docker-cleaner service on all worker nodes
                    docker service rm docker-cleaner-*
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
