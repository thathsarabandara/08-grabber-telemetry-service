pipeline {
    agent any

    environment {
        // Registry configurations (override these in Jenkins environment or UI params if needed)
        REGISTRY_CREDENTIALS_ID = 'docker-registry-credentials'
        REGISTRY_URL            = '' // Leave empty for Docker Hub, or specify e.g., '123456789012.dkr.ecr.us-east-1.amazonaws.com'
        IMAGE_NAME              = 'grabber-auth-service'
        IMAGE_TAG               = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                echo 'Setting up Python virtual environment and installing dependencies...'
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                echo 'Running linting checks (flake8 & bandit)...'
                sh '''
                    . venv/bin/activate
                    flake8 app/ tests/ --count --statistics
                    bandit -r app/ -q
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running unit tests with coverage reporting...'
                sh '''
                    . venv/bin/activate
                    pytest --cov=app --cov-report=term-missing tests/
                '''
            }
        }

        stage('Docker Build') {
            steps {
                echo 'Building Docker container image...'
                script {
                    def fullImageName = REGISTRY_URL ? "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}" : "${IMAGE_NAME}:${IMAGE_TAG}"
                    sh "docker build -t ${fullImageName} ."
                }
            }
        }

        stage('Docker Push') {
            steps {
                echo 'Pushing Docker image to registry...'
                script {
                    def fullImageName = REGISTRY_URL ? "${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}" : "${IMAGE_NAME}:${IMAGE_TAG}"
                    
                    if (REGISTRY_URL.contains('ecr')) {
                        // AWS ECR Push flow
                        def region = REGISTRY_URL.split('\\.')[3] ?: 'us-east-1'
                        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: REGISTRY_CREDENTIALS_ID]]) {
                            sh """
                                aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin ${REGISTRY_URL}
                                docker push ${fullImageName}
                            """
                        }
                    } else {
                        // Standard Docker Hub / Registry login & push
                        withCredentials([usernamePassword(credentialsId: REGISTRY_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASS')]) {
                            sh """
                                echo "${REGISTRY_PASS}" | docker login ${REGISTRY_URL ?: ''} -u "${REGISTRY_USER}" --password-stdin
                                docker push ${fullImageName}
                            """
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            echo 'Cleaning up workspace artifacts...'
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Please inspect build console logs.'
        }
    }
}
