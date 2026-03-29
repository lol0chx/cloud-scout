import SwiftUI

struct AIView: View {
    @EnvironmentObject var state: AppState
    @State private var messages: [ChatMessage] = []
    @State private var input = ""
    @State private var loading = false
    @FocusState private var focused: Bool

    private let suggestions = ["Who leads in scoring?", "Best record in the league?", "Predict the next game"]

    var body: some View {
        NavigationStack {
            ZStack { Color.appBg.ignoresSafeArea() }
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("AI Scout")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.bottom, 12)
                    SportPicker(sport: $state.sport)
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)

                ScrollViewReader { proxy in
                    ScrollView {
                        if messages.isEmpty {
                            VStack(spacing: 12) {
                                Text("🤖").font(.system(size: 44))
                                Text("AI Scout")
                                    .font(.system(size: 18, weight: .bold))
                                    .foregroundColor(.white)
                                Text("Ask about \(state.sport.rawValue) teams, players, matchups, or standings.")
                                    .font(.system(size: 14))
                                    .foregroundColor(.appSub)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 24)
                                ForEach(suggestions, id: \.self) { q in
                                    Button { input = q } label: {
                                        Text(q)
                                            .font(.system(size: 13))
                                            .foregroundColor(.appSub)
                                            .padding(.horizontal, 14)
                                            .padding(.vertical, 8)
                                            .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color.appBorder))
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
                        } else {
                            LazyVStack(spacing: 8) {
                                ForEach(messages) { msg in
                                    MessageBubble(message: msg)
                                }
                                if loading {
                                    HStack(spacing: 6) {
                                        ProgressView().tint(.appPrimary).scaleEffect(0.8)
                                        Text("Thinking...").font(.system(size: 13)).foregroundColor(.appSub)
                                        Spacer()
                                    }
                                    .padding(.horizontal, 16)
                                }
                                Color.clear.frame(height: 1).id("bottom")
                            }
                            .padding(.horizontal, 16)
                            .padding(.top, 8)
                        }
                    }
                    .onChange(of: messages.count) { _, _ in
                        withAnimation { proxy.scrollTo("bottom") }
                    }
                    .onChange(of: loading) { _, _ in
                        withAnimation { proxy.scrollTo("bottom") }
                    }
                }

                // Input bar
                HStack(alignment: .bottom, spacing: 8) {
                    TextField("Ask about \(state.sport.rawValue)...", text: $input, axis: .vertical)
                        .textFieldStyle(.plain)
                        .foregroundColor(.white)
                        .lineLimit(1...5)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(Color.appCard)
                        .clipShape(RoundedRectangle(cornerRadius: 20))
                        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color.appBorder))
                        .focused($focused)
                        .onSubmit { Task { await send() } }

                    Button { Task { await send() } } label: {
                        Image(systemName: "arrow.up")
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(.white)
                            .frame(width: 38, height: 38)
                            .background(input.trimmingCharacters(in: .whitespaces).isEmpty || loading ? Color.appBorder : Color.appPrimary)
                            .clipShape(Circle())
                    }
                    .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty || loading)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color.appBg)
                .overlay(alignment: .top) { Divider().background(Color.appBorder) }
            }
        }
        .onChange(of: state.sport) { _, _ in messages = [] }
    }

    private func send() async {
        let text = input.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !loading else { return }
        input = ""
        let userMsg = ChatMessage(role: "user", content: text)
        messages.append(userMsg)
        loading = true
        do {
            let reply = try await API.aiChat(league: state.sport, message: text, history: messages)
            messages.append(ChatMessage(role: "assistant", content: reply))
        } catch let e {
            messages.append(ChatMessage(role: "assistant", content: "Error: \(e.localizedDescription)"))
        }
        loading = false
    }
}

private struct MessageBubble: View {
    let message: ChatMessage
    private var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 50) }
            Text(message.content)
                .font(.system(size: 15))
                .foregroundColor(isUser ? .white : .white)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(isUser ? Color.appPrimary : Color.appCard)
                .clipShape(
                    .rect(
                        topLeadingRadius: 16,
                        bottomLeadingRadius: isUser ? 16 : 4,
                        bottomTrailingRadius: isUser ? 4 : 16,
                        topTrailingRadius: 16
                    )
                )
            if !isUser { Spacer(minLength: 50) }
        }
    }
}
