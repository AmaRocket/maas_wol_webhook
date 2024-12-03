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
