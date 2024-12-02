pipeline {
    agent any

    environment {
        API_KEY = credentials('maas-api-key') // Stored as 'consumer_key,token_key,token_secret'
    }

    stages {
        stage('Test MAAS API Token') {
            steps {
                script {
                    // Splitting the API_KEY into components
                    def apiKeyParts = API_KEY.split(':')
                    def consumerKey = apiKeyParts[0]
                    def tokenKey = apiKeyParts[1]
                    def tokenSecret = apiKeyParts[2]

                    // Generate nonce and timestamp
                    def oauthNonce = sh(script: "cat /proc/sys/kernel/random/uuid", returnStdout: true).trim()
                    def oauthTimestamp = sh(script: "date +%s", returnStdout: true).trim()

                    // Construct the OAuth header
                    def oauthHeader = """
                        Authorization: OAuth 
                        oauth_version="1.0", 
                        oauth_signature_method="PLAINTEXT", 
                        oauth_consumer_key="${consumerKey}", 
                        oauth_token="${tokenKey}", 
                        oauth_signature="&${tokenSecret}", 
                        oauth_nonce="${oauthNonce}", 
                        oauth_timestamp="${oauthTimestamp}"
                    """.trim().replaceAll("\\s+", " ")

                    // Execute the curl command
                    sh """
                        curl --header '${oauthHeader}' https://maas.dmi.unibas.ch/MAAS/api/2.0/machines/
                    """
                }
            }
        }
    }
}
