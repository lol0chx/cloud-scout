import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            GamesView()
                .tabItem { Label("Games", systemImage: "sportscourt") }
            StandingsView()
                .tabItem { Label("Standings", systemImage: "list.number") }
            PredictView()
                .tabItem { Label("Predict", systemImage: "chart.bar") }
            FormView()
                .tabItem { Label("Form", systemImage: "chart.line.uptrend.xyaxis") }
            PlayersView()
                .tabItem { Label("Players", systemImage: "person.2") }
            AIView()
                .tabItem { Label("AI Scout", systemImage: "brain") }
            UpdateView()
                .tabItem { Label("Update", systemImage: "arrow.down.circle") }
        }
        .tint(.appPrimary)
        .background(Color.appBg)
    }
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}
