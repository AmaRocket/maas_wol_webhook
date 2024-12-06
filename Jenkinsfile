pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key')
        RACK_SERVER = "10.34.64.1"
        REGION_SERVER = "10.34.64.2"
        REPO_URL = "git@github.com:AmaRocket/maas_wol_webhook.git"
    }

    stages {
        stage('Deploy to Rack Controller') {
            steps {
                sshagent(credentials: ['rack_server_ssh_credentials']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no localadmin@${RACK_SERVER} << 'EOF'
                        set -e

                        # Clone repository
                        if [ ! -d "maas-wol-webhook" ]; then
                            git clone ${REPO_URL} maas-wol-webhook
                        else
                            cd maas-wol-webhook && git pull
                        fi

                        # Install dependencies and run tests
                        cd maas-wol-webhook
                        sudo apt update && sudo apt install -y python3 python3-pip
                        pip3 install -r requirements.txt
                        pytest tests/

                        # Clean up dangling images
                        docker image prune -f

                        # Build Docker image
                        docker build -t maas-wol-webhook:latest .

                        # Stop and remove existing container if running
                        if docker ps -a -q -f name=maas_wol_container; then
                            docker stop maas_wol_container
                            docker rm -f maas_wol_container
                        fi

                        # Run the container
                        export MAAS_API_KEY=${MAAS_API_KEY}
                        docker run -d --network=host --env MAAS_API_KEY=${MAAS_API_KEY} \\
                            -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container \\
                            maas-wol-webhook:latest
                        EOF
                    """
                }
            }
        }

        stage('Deploy to Region Controller') {
            steps {
                sshagent(credentials: ['region_server_ssh_credentials']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no localadmin@${REGION_SERVER} << 'EOF'
                        set -e

                        # Clone repository
                        if [ ! -d "maas-wol-webhook" ]; then
                            git clone ${REPO_URL} maas-wol-webhook
                        else
                            cd maas-wol-webhook && git pull
                        fi

                        # Install dependencies and run tests
                        cd maas-wol-webhook
                        sudo apt update && sudo apt install -y python3 python3-pip
                        pip3 install -r requirements.txt
                        pytest tests/

                        # Clean up dangling images
                        docker image prune -f

                        # Build Docker image
                        docker build -t maas-wol-webhook:latest .

                        # Stop and remove existing container if running
                        if docker ps -a -q -f name=maas_wol_container; then
                            docker stop maas_wol_container
                            docker rm -f maas_wol_container
                        fi

                        # Run the container
                        export MAAS_API_KEY=${MAAS_API_KEY}
                        docker run -d --network=host --env MAAS_API_KEY=${MAAS_API_KEY} \\
                            -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container \\
                            maas-wol-webhook:latest
                        EOF
                    """
                }
            }
        }
    }

    post {
        success {
            echo 'Deployment successful on both Rack and Region Controllers!'
        }
        failure {
            echo 'Deployment failed. Check logs for errors.'
        }
    }
}
