pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key')
    }

    stages {
        stage('Clone Repository on Rack Controller') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
                    git branch: 'main', url: 'https://github.com/AmaRocket/maas_wol_webhook.git'
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    sh '''
                    sudo apt update
                    sudo apt install -y python3 python3-pip
                    pip3 install pytest
                    pip3 install -r requirements.txt
                    '''
                }
            }
        }

        stage('Run Tests on Rack Controller') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL/tests/') {
                    sh 'chmod +x tests.py'
                    sh 'python3 tests.py'
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
                        // Check if the image exists locally
                        echo "Checking if Docker image '${imageName}' exists..."
                        def imageExists = sh(script: "docker images -a -q ${imageName}", returnStdout: true).trim()

                        // If the image exists, remove it
                        if (imageExists) {
                            echo "Docker image '${imageName}' exists. Removing it..."
                            sh "docker rmi -f ${imageName}"
                        } else {
                            echo "Docker image '${imageName}' does not exist. Proceeding to build..."
                        }
                        // Create a Docker image
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
                        // Stop and remove the container if it is running
                        sh "docker stop maas_wol_container"
                        sh "docker rm -f maas_wol_container"
                        sh "docker image prune -f"
                    } else {
                        echo "No running container found. Proceeding to start a new one."
                    }

                    withCredentials([string(credentialsId: 'maas-api-key', variable: 'MAAS_API_KEY')]) {
                        sh '''
                        export MAAS_API_KEY=$MAAS_API_KEY
                        docker run -d --network=host --env MAAS_API_KEY=$MAAS_API_KEY -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook:latest
                        '''
                    }
                }
            }
        }

        stage('Test Region Connection via SSH'){
            steps {
                sshagent(['rack_server_ssh_credentials']) {
                    sh '''
                    ssh -o StrictHostKeyChecking=no localadmin@10.34.64.2 "echo Connection Successful!"
                        cd /var/lib/jenkins/workspace/WOL
                        git pull
                        docker image prune -f
                        docker rmi -f maas-wol-webhook
                        docker build -t maas-wol-webhook:latest .
                        docker stop maas_wol_container || true
                        docker rm -f maas_wol_container || true
                        export MAAS_API_KEY=$MAAS_API_KEY
                        docker run -d --network=host --env MAAS_API_KEY=$MAAS_API_KEY -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook:latest
                        docker image prune -f
                    '''
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
