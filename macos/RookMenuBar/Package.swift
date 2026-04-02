// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "RookMenuBar",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "RookMenuBar", targets: ["RookMenuBar"]),
    ],
    targets: [
        .executableTarget(
            name: "RookMenuBar",
            path: "Sources/RookMenuBar"
        ),
    ]
)
