import SwiftUI

struct AIView: View {
    @EnvironmentObject var state: AppState
    @State private var messages: [ChatMessage] = []
    @State private var input = ""
    @State private var loading = false
    @FocusState private var focused: Bool

    private var sportSuggestions: [String] {
        state.sport == .NBA
            ? ["Lakers injury update", "Top 3 MVP candidates", "Predict tonight's slate"]
            : ["Yankees rotation", "Best ERA this season", "Predict tonight's games"]
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.csDarkBg.ignoresSafeArea()
                VStack(spacing: 0) {
                    header
                        .padding(.horizontal, 20)
                        .padding(.top, 6)
                        .padding(.bottom, 14)

                    chatScroll
                    composer
                }
            }
            .toolbar(.hidden, for: .navigationBar)
        }
        .preferredColorScheme(.dark)
        .onChange(of: state.sport) { _, _ in messages = [] }
    }

    // MARK: - Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [Color(hex: "5b8ff7"), Color(hex: "8b5cf6")],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    Image(systemName: "sparkles")
                        .font(.system(size: 16, weight: .heavy))
                        .foregroundColor(.white)
                }
                .frame(width: 34, height: 34)

                Text("AI Scout")
                    .font(.csEditorial(32))
                    .foregroundColor(.white)

                Spacer()

                Text(state.sport.rawValue)
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(.csDarkPrimary)
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(Color.csDarkPrimary.opacity(0.15))
                    .clipShape(Capsule())
            }
            Text("Ask about teams, players, matchups, standings.")
                .font(.system(size: 13))
                .foregroundColor(.csDarkSub)
        }
    }

    // MARK: - Chat scroll

    private var chatScroll: some View {
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(messages) { msg in
                        MessageBubble(message: msg)
                    }
                    if loading {
                        HStack(spacing: 8) {
                            ProgressView().tint(.csDarkPrimary).scaleEffect(0.8)
                            Text("Thinking…")
                                .font(.system(size: 13))
                                .foregroundColor(.csDarkSub)
                            Spacer()
                        }
                        .padding(.horizontal, 4)
                    }
                    if messages.isEmpty {
                        emptyState
                    }
                    suggestionPills
                        .padding(.top, 4)
                    Color.clear.frame(height: 1).id("bottom")
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
            }
            .onChange(of: messages.count) { _, _ in withAnimation { proxy.scrollTo("bottom") } }
            .onChange(of: loading) { _, _ in withAnimation { proxy.scrollTo("bottom") } }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "sparkles")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.csDarkPrimary)
            Text("Start a conversation")
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(.white)
            Text("Tap a suggestion below or type your own question about \(state.sport.rawValue).")
                .font(.system(size: 12))
                .foregroundColor(.csDarkSub)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 30)
    }

    private var suggestionPills: some View {
        FlowLayout(spacing: 8, lineSpacing: 8) {
            ForEach(sportSuggestions, id: \.self) { s in
                Button { input = s } label: {
                    Text(s)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.csDarkSub)
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .overlay(
                            Capsule().strokeBorder(Color.csDarkBorder, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Composer

    private var composer: some View {
        HStack(spacing: 10) {
            TextField("", text: $input, axis: .vertical)
                .textFieldStyle(.plain)
                .foregroundColor(.white)
                .tint(.csDarkPrimary)
                .lineLimit(1...4)
                .placeholder(when: input.isEmpty) {
                    Text("Ask about \(state.sport.rawValue)…")
                        .foregroundColor(.csDarkSub)
                        .font(.system(size: 14))
                }
                .padding(.horizontal, 16).padding(.vertical, 10)
                .background(Color.csDarkCard)
                .overlay(
                    RoundedRectangle(cornerRadius: 22, style: .continuous)
                        .strokeBorder(Color.csDarkBorder, lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                .focused($focused)
                .onSubmit { Task { await send() } }

            let canSend = !input.trimmingCharacters(in: .whitespaces).isEmpty && !loading
            Button { Task { await send() } } label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundColor(.white)
                    .frame(width: 40, height: 40)
                    .background(canSend ? Color.csDarkPrimary : Color.csDarkBorder)
                    .clipShape(Circle())
            }
            .disabled(!canSend)
        }
        .padding(.horizontal, 14).padding(.top, 10).padding(.bottom, 12)
        .background(Color.csDarkBg)
        .overlay(alignment: .top) {
            Rectangle().fill(Color.csDarkBorder).frame(height: 1)
        }
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

// MARK: - Message bubble

private struct MessageBubble: View {
    let message: ChatMessage
    private var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 50) }
            Text(message.content)
                .font(.system(size: 14))
                .foregroundColor(.white)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(bubbleBackground)
                .clipShape(
                    .rect(
                        topLeadingRadius: 16,
                        bottomLeadingRadius: isUser ? 16 : 4,
                        bottomTrailingRadius: isUser ? 4 : 16,
                        topTrailingRadius: 16
                    )
                )
                .overlay(
                    UnevenRoundedRectangle(
                        cornerRadii: .init(
                            topLeading: 16,
                            bottomLeading: isUser ? 16 : 4,
                            bottomTrailing: isUser ? 4 : 16,
                            topTrailing: 16
                        ),
                        style: .continuous
                    )
                    .strokeBorder(isUser ? Color.clear : Color.csDarkBorder, lineWidth: 1)
                )
            if !isUser { Spacer(minLength: 50) }
        }
    }

    @ViewBuilder
    private var bubbleBackground: some View {
        if isUser {
            LinearGradient(
                colors: [Color(hex: "5b8ff7"), Color(hex: "4070e0")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        } else {
            Color.csDarkCard
        }
    }
}

// MARK: - Placeholder helper

private extension View {
    @ViewBuilder
    func placeholder<Content: View>(when shouldShow: Bool, @ViewBuilder placeholder: () -> Content) -> some View {
        ZStack(alignment: .leading) {
            if shouldShow { placeholder() }
            self
        }
    }
}

// MARK: - Simple flow layout for suggestion pills

private struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    var lineSpacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        return layout(in: width, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = layout(in: bounds.width, subviews: subviews)
        for (subview, offset) in zip(subviews, result.offsets) {
            subview.place(at: CGPoint(x: bounds.minX + offset.x, y: bounds.minY + offset.y), proposal: .unspecified)
        }
    }

    private func layout(in maxWidth: CGFloat, subviews: Subviews) -> (offsets: [CGPoint], size: CGSize) {
        var offsets: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var lineHeight: CGFloat = 0
        var totalWidth: CGFloat = 0

        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            if x + size.width > maxWidth, x > 0 {
                x = 0
                y += lineHeight + lineSpacing
                lineHeight = 0
            }
            offsets.append(CGPoint(x: x, y: y))
            x += size.width + spacing
            lineHeight = max(lineHeight, size.height)
            totalWidth = max(totalWidth, x - spacing)
        }
        return (offsets, CGSize(width: totalWidth, height: y + lineHeight))
    }
}
