require 'json'

package = JSON.parse(File.read(File.join(__dir__, '..', 'package.json'))) rescue {}

Pod::Spec.new do |s|
  s.name           = 'VpnRouterNative'
  s.version        = package['version'] || '0.1.0'
  s.summary        = 'Expo native VPN bridge for VPN Router'
  s.description    = 'A native module boundary for controlling Android VpnService and iOS Network Extension VPN profiles.'
  s.author         = 'VPN Router'
  s.homepage       = 'https://github.com/faafaafuu/VPP-WL-mobile-'
  s.platforms      = { :ios => '15.0' }
  s.source         = { :path => '.' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'
  s.frameworks = 'NetworkExtension'
  s.source_files = 'Sources/**/*.{swift}'
end
