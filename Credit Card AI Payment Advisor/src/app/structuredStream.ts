export async function readStructuredSse(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: Record<string, any>) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';

    for (const chunk of chunks) {
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'));
      if (!dataLine) continue;

      try {
        onEvent(JSON.parse(dataLine.replace(/^data:\s*/, '')));
      } catch {
        // Ignore malformed SSE events.
      }
    }
  }
}
