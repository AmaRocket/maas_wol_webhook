pipeline {
    agent any

    environment {
        MAAS_API_KEY = credentials('maas-api-key') //MAAS API TOKEN Assuming the token is stored in Jenkins credentials
    }

    stages {
        stage('Test MAAS API Token') {
            steps {
                script {
                    // Testing if the MAAS API token is valid
                    def response = httpRequest(
                        url: 'https://maas.dmi.unibas.ch/MAAS/api/2.0/machines', 
                        customHeaders: [[name: 'Authorization', value: "Bearer ${MAAS_API_KEY}"]],
                        validResponseCodes: '200:299', 
                        consoleLogResponseBody: true
                    )
                    
                    echo "API Response: ${response}"
                }
            }
        }
    }
}
