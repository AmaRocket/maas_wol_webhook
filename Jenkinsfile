pipeline {
    agent any

    environment {
        API_KEY = credentials('maas-api-key') // Assuming this is where your API keys are stored
    }

    stages {
        stage('Test MAAS API Token') {
            steps {
                script {
                    // Constructing the OAuth header and running the curl command
                    def oauthHeader = "Authorization: OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key=${API_KEY[0]}, oauth_token=${API_KEY[1]}, oauth_signature=&${API_KEY[2]}, oauth_nonce=\$(uuid), oauth_timestamp=\$(date +%s)"
                    
                    // Running the curl command to test the MAAS API
                    sh """
                        curl --header "${oauthHeader}" https://maas.dmi.unibas.ch/MAAS/api/2.0/machines/
                    """
                }
            }
        }
    }
}
