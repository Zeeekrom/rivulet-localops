using './main.bicep'

param location = 'newzealandnorth'
param containerImage = 'ghcr.io/zeeekrom/rivulet-localops:v0.8.0'
param namePrefix = 'rivulet-demo'
param release = 'v0.8.0'
param expiresOn = '2026-10-24'
