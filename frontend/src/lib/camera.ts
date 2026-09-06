export async function getCameraStream(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user", width: { ideal: 720 }, height: { ideal: 960 } },
    audio: false,
  });
}

export function stopCameraStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

// Samples the current video frame onto a hidden canvas and returns 0-100 brightness.
export function measureBrightness(video: HTMLVideoElement, canvas: HTMLCanvasElement): number {
  const ctx = canvas.getContext("2d");
  if (!ctx || video.videoWidth === 0) return 0;

  canvas.width = 64;
  canvas.height = 64;
  ctx.drawImage(video, 0, 0, 64, 64);

  const { data } = ctx.getImageData(0, 0, 64, 64);
  let total = 0;
  for (let i = 0; i < data.length; i += 4) {
    total += (data[i] + data[i + 1] + data[i + 2]) / 3;
  }
  return Math.round((total / (data.length / 4) / 255) * 100);
}

export function captureFrame(video: HTMLVideoElement, canvas: HTMLCanvasElement): string {
  const ctx = canvas.getContext("2d");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx?.drawImage(video, 0, 0);
  return canvas.toDataURL("image/jpeg", 0.9);
}