export const C = {
  bg: '#0d0d0d',
  card: '#1c1c2e',
  border: '#2a2a3e',
  primary: '#5b8ff7',
  win: '#2ea44f',
  loss: '#cf222e',
  text: '#ffffff',
  sub: '#8a8a9a',
  nba: '#5b8ff7',
  mlb: '#d4b86a',
} as const;

export const S = {
  screen: {
    flex: 1,
    backgroundColor: C.bg,
  },
  card: {
    backgroundColor: C.card,
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  row: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
  },
  label: {
    color: C.sub,
    fontSize: 12,
    marginBottom: 2,
  },
  value: {
    color: C.text,
    fontSize: 16,
    fontWeight: '600' as const,
  },
  title: {
    color: C.text,
    fontSize: 20,
    fontWeight: '700' as const,
    marginBottom: 12,
  },
  section: {
    color: C.sub,
    fontSize: 13,
    fontWeight: '600' as const,
    letterSpacing: 0.8,
    textTransform: 'uppercase' as const,
    marginBottom: 8,
    marginTop: 16,
  },
} as const;
