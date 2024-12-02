pipeline {
    agent any

    stages {
        stage('Clone Repository') {
            steps {
                dir('/usr/local/maas_wol_service/WOL') {
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
                dir('/usr/local/maas_wol_service/WOL') {
                script {
                    // Run tests using pytest
                    sh '/tests/tests.py'
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
}