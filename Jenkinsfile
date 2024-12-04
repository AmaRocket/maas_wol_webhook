pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key') // Stored as 'consumer_key,token_key,token_secret'
    }

    stages {
        stage('Clone Repository') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
                    git branch: 'main', url: 'https://github.com/AmaRocket/maas_wol_webhook.git'
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    // Install required dependencies using pip
                    sh '''
                    sudo apt update
                    sudo apt install -y python3 python3-pip
                    pip3 install pytest
                    pip3 install -r requirements.txt
                    '''
                }
            }
        }

        stage('Run Tests') {
            steps {
                    dir('/var/lib/jenkins/workspace/WOL/tests/') {
                    script {
                        // Run tests using pytest
                        sh 'chmod +x tests.py'
                        sh 'python3 tests.py'
                        sh 'export MAAS_API_KEY=$MAAS_API_KEY'

                    }
                }
            }
        }

    stage('Build Docker Image') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
                    script {
                        // Define Docker image name and tag
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
                        sh '''
                        docker build -t maas-wol-webhook .
                        '''
                    }
                }
            }
        }

    stage('Check and Restart Container') {
            steps {
                script {
                    def runningContainer = sh(script: "docker ps -a -q -f name=maas_wol_container", returnStdout: true).trim()

                    if (runningContainer) {
                        echo "Stopping and removing existing container..."
                        // Stop and remove the container if it is running
                        sh "docker stop maas_wol_container"
                        sh "docker rm -f maas_wol_container"
                    } else {
                        echo "No running container found. Proceeding to start a new one."
                    }

                    // Run a new container with the updated image
                    echo "Starting a new container with the updated image..."
                    sh 'docker run -d --env MAAS_API_KEY=$MAAS_API_KEY  -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook  && echo $MAAS_API_KEY'

//                     sh 'docker run -d --network=host --env-file /etc/docker/maas_api_key.env -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook:latest'
                }
            }
        }
    }

    post {
        success {
            echo 'All stages passed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check logs for errors.'
        }
    }
}
