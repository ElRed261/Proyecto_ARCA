import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DateField from '../shared/components/DateField';

describe('DateField — comportamiento del componente', () => {
    it('tipear 15082026 commitea ISO 2026-08-15', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<DateField value="" onChange={onChange} />);
        const input = screen.getByLabelText('Fecha (DD/MM/AAAA)');
        await user.type(input, '15082026');
        expect(input.value).toBe('15/08/2026');
        expect(onChange).toHaveBeenCalledWith('2026-08-15');
    });

    it('fecha imposible NO commitea y marca error visual', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<DateField value="" onChange={onChange} />);
        const input = screen.getByLabelText('Fecha (DD/MM/AAAA)');
        await user.type(input, '31022026');
        expect(onChange).not.toHaveBeenCalled();
        expect(input.getAttribute('aria-invalid')).toBe('true');
    });

    it('refleja el valor ISO que manda el padre', () => {
        const noop = () => {};
        const { rerender } = render(<DateField value="2026-08-15" onChange={noop} />);
        expect(screen.getByLabelText('Fecha (DD/MM/AAAA)').value).toBe('15/08/2026');
        rerender(<DateField value="2026-08-16" onChange={noop} />);
        expect(screen.getByLabelText('Fecha (DD/MM/AAAA)').value).toBe('16/08/2026');
    });
});
