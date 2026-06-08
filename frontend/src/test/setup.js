import '@testing-library/jest-dom/vitest';

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: async () => [],
    }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});
