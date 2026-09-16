targetScope = 'resourceGroup'

@description('Azure region for the public portfolio sandbox.')
param location string = resourceGroup().location

@description('Public OCI image, including an immutable release tag.')
param containerImage string

@description('Short resource-name prefix.')
@minLength(3)
@maxLength(20)
param namePrefix string = 'rivulet-demo'

@description('Release label exposed to the container.')
param release string = 'v0.7.0'

@description('ISO date after which the demo resources should be reviewed or removed.')
param expiresOn string

var commonTags = {
  project: 'rivulet-localops'
  environment: 'portfolio-demo'
  managedBy: 'bicep-github-oidc'
  dataClass: 'synthetic-and-public-reference-only'
  expiresOn: expiresOn
}

resource environment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: '${namePrefix}-env'
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'none'
    }
    publicNetworkAccess: 'Enabled'
  }
}

resource app 'Microsoft.App/containerApps@2026-01-01' = {
  name: namePrefix
  location: location
  tags: commonTags
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'rivulet-web'
          image: containerImage
          env: [
            {
              name: 'RIVULET_DEPLOYMENT_PROFILE'
              value: 'public_demo'
            }
            {
              name: 'RIVULET_RELEASE'
              value: release
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 8
              periodSeconds: 30
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 3
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

output applicationName string = app.name
output applicationUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output environmentName string = environment.name
output minimumReplicas int = app.properties.template.scale.minReplicas
output maximumReplicas int = app.properties.template.scale.maxReplicas
