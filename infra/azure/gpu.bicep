targetScope = 'resourceGroup'

@description('Italy North only for this proof of concept.')
@allowed(['italynorth'])
param location string = 'italynorth'

@description('Unique short deployment name. Do not reuse another project resources.')
@minLength(3)
@maxLength(30)
param name string

@allowed(['Standard_NC4as_T4_v3'])
param vmSize string = 'Standard_NC4as_T4_v3'

@description('Public SSH key only. Never pass a private key or model token.')
@minLength(20)
param sshPublicKey string

@description('Restrict SSH to an approved operator IPv4 /32 address.')
param sshSourceCidr string

@description('UTC time HHmm for Azure auto-shutdown (deallocation); set near the approved batch deadline.')
@minLength(4)
@maxLength(4)
param shutdownTimeUtc string

@description('ISO 8601 expiry for scheduled cleanup checks. A tag alone does not delete resources.')
param expiresAt string

var tags = {
  project: '3d-scene-toolchain'
  managedBy: 'scene-toolchain'
  expiresAt: expiresAt
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${name}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'operator-ssh'
        properties: {
          priority: 1000
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourceAddressPrefix: sshSourceCidr
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
        }
      }
    ]
  }
}

resource network 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: '${name}-network'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: ['10.46.0.0/16']
    }
    subnets: [
      {
        name: 'worker'
        properties: {
          addressPrefix: '10.46.1.0/24'
          networkSecurityGroup: { id: nsg.id }
        }
      }
    ]
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = {
  name: '${name}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource nic 'Microsoft.Network/networkInterfaces@2023-09-01' = {
  name: '${name}-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'worker'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: { id: resourceId('Microsoft.Network/virtualNetworks/subnets', network.name, 'worker') }
          publicIPAddress: { id: publicIp.id }
        }
      }
    ]
  }
}

resource worker 'Microsoft.Compute/virtualMachines@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    hardwareProfile: { vmSize: vmSize }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        deleteOption: 'Delete'
        diskSizeGB: 128
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
      }
    }
    osProfile: {
      computerName: name
      adminUsername: 'scene'
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            { path: '/home/scene/.ssh/authorized_keys', keyData: sshPublicKey }
          ]
        }
      }
    }
    networkProfile: {
      networkInterfaces: [{ id: nic.id, properties: { deleteOption: 'Delete' } }]
    }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
  }
}

resource driver 'Microsoft.Compute/virtualMachines/extensions@2023-09-01' = {
  parent: worker
  name: 'NvidiaGpuDriverLinux'
  location: location
  properties: {
    publisher: 'Microsoft.HpcCompute'
    type: 'NvidiaGpuDriverLinux'
    typeHandlerVersion: '1.9'
    autoUpgradeMinorVersion: true
  }
}

resource shutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${worker.name}'
  location: location
  tags: tags
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: { time: shutdownTimeUtc }
    timeZoneId: 'UTC'
    targetResourceId: worker.id
    notificationSettings: { status: 'Disabled', timeInMinutes: 30 }
  }
}

output vmName string = worker.name
output publicIpAddress string = publicIp.properties.ipAddress
