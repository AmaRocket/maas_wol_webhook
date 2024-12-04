pipeline {
    agent any

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
                }
            }
        }
    }

    stage('Build Docker Image') {
            steps {
                dir('/var/lib/jenkins/workspace/WOL') {
                    script {
                        // Create a Docker image
                        sh '''
                        docker build -t maas-wol-webhook:latest .
                        '''
                    }
                }
            }
        }

    stage('Check and Restart Container') {
            steps {
                script {
                    // Get the MAAS_API_KEY from Jenkins credentials
                    def maasApiKey = credentials('maas-api-key')
                    echo "This is API Key: ${maasApiKey}"
                    // Check if a container is running with the name "maas_wol_container"
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
                    sh 'docker run -d --network=host -e MAAS_API_KEY=${maasApiKey} -v /home/user/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook:latest'
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
