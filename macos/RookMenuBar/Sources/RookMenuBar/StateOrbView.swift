import SwiftUI

struct StateOrbView: View {
    let state: RuntimeState
    let audioBars: [Double]
    let speakingLevel: Double

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 0.2 : 1.0 / 30.0)) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate

            ZStack {
                RoundedRectangle(cornerRadius: 32, style: .continuous)
                    .fill(Color.white.opacity(0.05))
                    .overlay(
                        RoundedRectangle(cornerRadius: 32, style: .continuous)
                            .stroke(Color.white.opacity(0.08), lineWidth: 1)
                    )

                Circle()
                    .fill(coreGradient)
                    .frame(width: 122, height: 122)
                    .shadow(color: state.tint.opacity(0.42), radius: 26)
                    .scaleEffect(coreScale(for: time))
                    .overlay {
                        Image(systemName: state.symbolName)
                            .font(.system(size: 34, weight: .black))
                            .foregroundStyle(.white.opacity(0.96))
                    }

                Circle()
                    .stroke(state.tint.opacity(0.42), lineWidth: 1.2)
                    .frame(width: 152, height: 152)
                    .scaleEffect(outerRingScale(for: time))
                    .blur(radius: 0.2)

                if state == .processing {
                    ProcessingHalo(phase: time, tint: state.tint, reduceMotion: reduceMotion)
                }

                if state == .listening {
                    ListeningBarsView(bars: audioBars, tint: state.tint)
                        .padding(.horizontal, 40)
                }

                if state == .speaking {
                    SpeakingWaveView(level: speakingLevel, tint: state.tint, phase: time)
                        .padding(.horizontal, 32)
                }
            }
        }
    }

    private var coreGradient: LinearGradient {
        LinearGradient(
            colors: [
                state.tint.opacity(0.92),
                state.tint.opacity(0.55),
                Color.white.opacity(0.14),
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    private func coreScale(for time: TimeInterval) -> CGFloat {
        guard !reduceMotion else {
            return state == .listening ? 1.02 : 1.0
        }

        switch state {
        case .idle:
            return 1.0 + CGFloat(sin(time * 1.2)) * 0.015
        case .listening:
            return 1.02 + CGFloat(max(audioBars.max() ?? 0.05, 0.06)) * 0.08
        case .processing:
            return 1.02 + CGFloat(sin(time * 2.4)) * 0.03
        case .speaking:
            return 1.0 + CGFloat(max(speakingLevel, 0.05)) * 0.1
        case .error:
            return 0.98 + CGFloat(sin(time * 6.0)) * 0.018
        case .unknown:
            return 1.0
        }
    }

    private func outerRingScale(for time: TimeInterval) -> CGFloat {
        guard !reduceMotion else {
            return state == .speaking ? 1.05 : 1.0
        }
        switch state {
        case .listening:
            return 1.02 + CGFloat(max(audioBars.max() ?? 0.05, 0.08)) * 0.18
        case .processing:
            return 1.04 + CGFloat(sin(time * 1.6)) * 0.04
        case .speaking:
            return 1.04 + CGFloat(max(speakingLevel, 0.05)) * 0.16
        default:
            return 1.0
        }
    }
}

private struct ProcessingHalo: View {
    let phase: TimeInterval
    let tint: Color
    let reduceMotion: Bool

    var body: some View {
        ZStack {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .trim(from: 0.08, to: 0.42)
                    .stroke(
                        tint.opacity(0.35 - Double(index) * 0.08),
                        style: StrokeStyle(lineWidth: 9 - CGFloat(index) * 2, lineCap: .round)
                    )
                    .frame(width: 156 + CGFloat(index) * 24, height: 156 + CGFloat(index) * 24)
                    .rotationEffect(.degrees(rotation(for: index)))
            }
        }
    }

    private func rotation(for index: Int) -> Double {
        guard !reduceMotion else {
            return Double(index) * 60.0
        }
        return phase * (28.0 - Double(index) * 6.0) + Double(index) * 80.0
    }
}

private struct ListeningBarsView: View {
    let bars: [Double]
    let tint: Color

    var body: some View {
        VStack {
            Spacer()
            HStack(alignment: .bottom, spacing: 7) {
                ForEach(Array(bars.enumerated()), id: \.offset) { _, value in
                    Capsule()
                        .fill(tint.opacity(0.92))
                        .frame(width: 9, height: 18 + max(8, value * 76))
                }
            }
            .padding(.bottom, 28)
        }
    }
}

private struct SpeakingWaveView: View {
    let level: Double
    let tint: Color
    let phase: TimeInterval

    var body: some View {
        Canvas { context, size in
            let midY = size.height * 0.70
            let baseAmplitude = CGFloat(12 + max(level, 0.06) * 42)

            for line in 0..<3 {
                var path = Path()
                let step = max(size.width / 48, 8)
                let frequency = 0.028 + Double(line) * 0.008
                let amplitude = baseAmplitude - CGFloat(line) * 7
                path.move(to: CGPoint(x: 0, y: midY))

                for x in stride(from: CGFloat.zero, through: size.width, by: step) {
                    let wave = sin((Double(x) * frequency) + phase * (2.2 + Double(line) * 0.7))
                    let y = midY + CGFloat(wave) * amplitude
                    path.addLine(to: CGPoint(x: x, y: y))
                }

                context.stroke(
                    path,
                    with: .color(tint.opacity(0.8 - Double(line) * 0.16)),
                    style: StrokeStyle(lineWidth: 5 - CGFloat(line), lineCap: .round, lineJoin: .round)
                )
            }
        }
        .padding(.top, 84)
    }
}
