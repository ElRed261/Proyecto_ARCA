import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  AAXX,
  CONST_333,
  CONST_555,
  HOURS,
  EVEN_HOURS,
  ODD_HOURS,
  normalizePressure,
  formatDateDisplay,
  toISODate,
  getTodayISO,
  createInitialObservations,
  hasTemperatureData,
  safeValue,
} from './synopticUtils';

describe('synopticUtils constants', () => {
  it('exports synoptic message constants', () => {
    expect(AAXX).toBe('AAXX');
    expect(CONST_333).toBe('333');
    expect(CONST_555).toBe('555');
  });

  it('exports the expected observation hour lists', () => {
    expect(HOURS).toEqual(['06Z', '09Z', '12Z', '15Z', '18Z', '21Z', '00Z', '03Z']);
    expect(EVEN_HOURS).toEqual(['00Z', '06Z', '12Z', '18Z']);
    expect(ODD_HOURS).toEqual(['03Z', '09Z', '15Z', '21Z']);
  });
});

describe('normalizePressure', () => {
  it('adds 1000 to short pressure values', () => {
    expect(normalizePressure('15.3')).toBe('1015.3');
    expect(normalizePressure('5')).toBe('1005.0');
    expect(normalizePressure('99.9')).toBe('1099.9');
  });

  it('returns full pressure values unchanged', () => {
    expect(normalizePressure('1015.3')).toBe('1015.3');
    expect(normalizePressure('1000')).toBe('1000');
  });

  it('returns empty string for null, undefined or empty input', () => {
    expect(normalizePressure(null)).toBe('');
    expect(normalizePressure(undefined)).toBe('');
    expect(normalizePressure('')).toBe('');
    expect(normalizePressure('   ')).toBe('');
  });

  it('returns the original input for non-numeric values', () => {
    expect(normalizePressure('abc')).toBe('abc');
  });
});

describe('formatDateDisplay', () => {
  it('formats YYYY-MM-DD to dd/mm/aaaa', () => {
    expect(formatDateDisplay('2024-03-15')).toBe('15/03/2024');
  });

  it('formats DDMMYYYY to dd/mm/aaaa', () => {
    expect(formatDateDisplay('15032024')).toBe('15/03/2024');
  });

  it('returns empty string for null, undefined or empty input', () => {
    expect(formatDateDisplay(null)).toBe('');
    expect(formatDateDisplay(undefined)).toBe('');
    expect(formatDateDisplay('')).toBe('');
  });

  it('returns the original value for unknown formats', () => {
    expect(formatDateDisplay('invalid')).toBe('invalid');
  });
});

describe('toISODate', () => {
  it('returns ISO strings unchanged', () => {
    expect(toISODate('2024-03-15')).toBe('2024-03-15');
  });

  it('converts DDMMYYYY to YYYY-MM-DD', () => {
    expect(toISODate('15032024')).toBe('2024-03-15');
  });

  it('returns empty string for null, undefined or empty input', () => {
    expect(toISODate(null)).toBe('');
    expect(toISODate(undefined)).toBe('');
    expect(toISODate('')).toBe('');
  });

  it('returns the original value for unknown formats', () => {
    expect(toISODate('random')).toBe('random');
  });
});

describe('getTodayISO', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-07-02T12:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns today in YYYY-MM-DD format', () => {
    expect(getTodayISO()).toBe('2024-07-02');
  });
});

describe('createInitialObservations', () => {
  it('creates an observation entry for every synoptic hour', () => {
    const observations = createInitialObservations();

    expect(Object.keys(observations)).toEqual(HOURS);
    HOURS.forEach((hour) => {
      expect(observations[hour]).toEqual({});
    });
  });
});

describe('hasTemperatureData', () => {
  it('returns true when any hour has ts or th data', () => {
    const observations = createInitialObservations();
    observations['12Z'] = { ts: '25.3' };
    expect(hasTemperatureData(observations)).toBe(true);

    const withTh = createInitialObservations();
    withTh['06Z'] = { th: '18.0' };
    expect(hasTemperatureData(withTh)).toBe(true);
  });

  it('returns false when observations are empty', () => {
    expect(hasTemperatureData(createInitialObservations())).toBe(false);
    expect(hasTemperatureData({})).toBe(false);
  });

  it('returns false when observations are null', () => {
    expect(hasTemperatureData(null)).toBe(false);
    expect(hasTemperatureData(undefined)).toBe(false);
  });

  it('ignores whitespace-only values', () => {
    const observations = createInitialObservations();
    observations['12Z'] = { ts: '   ' };
    expect(hasTemperatureData(observations)).toBe(false);
  });
});

describe('safeValue', () => {
  it('converts valid values to strings', () => {
    expect(safeValue(25.3)).toBe('25.3');
    expect(safeValue('hello')).toBe('hello');
    expect(safeValue(0)).toBe('0');
    expect(safeValue(false)).toBe('false');
  });

  it('returns empty string for null and undefined', () => {
    expect(safeValue(null)).toBe('');
    expect(safeValue(undefined)).toBe('');
  });
});
