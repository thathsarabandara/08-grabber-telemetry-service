pipeline {
    agent any

    environment {
        REGISTRY_CREDENTIALS_ID = 'docker-registry-credentials'
        DOCKER_HUB_USER         = 'thathsarabandara'
        IMAGE_NAME              = "${DOCKER_HUB_USER}/grabber-telemetry-service"
        IMAGE_TAG               = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Environment Check') {
            steps {
                echo 'Verifying Python, pip, and Docker are available...'
                sh '''
                    python3 --version
                    pip3 --version
                    docker --version
                '''
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
                echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
                sh """
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                    docker tag  ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
                """
            }
        }

        stage('Docker Push') {
            steps {
                echo "Pushing Docker image to Docker Hub: ${IMAGE_NAME}"
                withCredentials([usernamePassword(
                    credentialsId: REGISTRY_CREDENTIALS_ID,
                    usernameVariable: 'REGISTRY_USER',
                    passwordVariable: 'REGISTRY_PASS'
                )]) {
                    sh """
                        echo "\${REGISTRY_PASS}" | docker login -u "\${REGISTRY_USER}" --password-stdin
                        docker push ${IMAGE_NAME}:${IMAGE_TAG}
                        docker push ${IMAGE_NAME}:latest
                        echo "Pushed ${IMAGE_NAME}:${IMAGE_TAG} and ${IMAGE_NAME}:latest"
                    """
                }
            }
        }
    }

    post {
        always {
            echo 'Logging out from Docker registry...'
            sh 'docker logout || true'
            echo 'Cleaning up workspace...'
            cleanWs()
        }
        success {
            echo "Pipeline SUCCESS — ${IMAGE_NAME}:${IMAGE_TAG} is live on Docker Hub!"
        }
        failure {
            echo 'Pipeline FAILED — check console output above for details.'
        }
    }
}
