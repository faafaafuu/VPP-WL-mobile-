import SwiftUI

struct ContentView: View {
    @State private var status: String = "Ready"

    var body: some View {
        VStack(spacing: 16) {
            Text(status)
            Button("Connect") {
                status = "Preparing VPN"
            }
        }
        .padding()
    }
}

