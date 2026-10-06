// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DiarizationBenchmarkHelper",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/FluidInference/FluidAudio.git", exact: "0.17.5")
    ],
    targets: [
        .executableTarget(
            name: "diarization-helper",
            dependencies: [.product(name: "FluidAudio", package: "FluidAudio")],
            path: "Sources/DiarizationHelper"
        )
    ]
)
