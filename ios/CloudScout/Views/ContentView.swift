import SwiftUI

struct ContentView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        TabView(selection: $state.selectedTab) {
            HomeView()
                .tabItem { Label("Home", systemImage: "house.fill") }
                .tag(0)
            GamesView()
                .tabItem { Label("Games", systemImage: "sportscourt") }
                .tag(1)
            StandingsView()
                .tabItem { Label("Standings", systemImage: "list.number") }
                .tag(2)
            PredictView()
                .tabItem { Label("Predict", systemImage: "chart.bar") }
                .tag(3)
            PlayersView()
                .tabItem { Label("Players", systemImage: "person.2") }
                .tag(4)
            AIView()
                .tabItem { Label("AI Scout", systemImage: "brain") }
                .tag(5)
            FormView()
                .tabItem { Label("Form", systemImage: "chart.line.uptrend.xyaxis") }
                .tag(6)
            UpdateView()
                .tabItem { Label("Update", systemImage: "arrow.down.circle") }
                .tag(7)
        }
        .tint(.appPrimary)
        .background(Color.appBg)
    }
}

#Preview {
    ContentView()
        .environmentObject(AppState())
}
