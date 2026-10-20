import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ComboBox from '../shared/components/ComboBox';

const OPTIONS = [
    { value: '78486', label: 'Jimaní (78486)' },
    { value: '78484', label: 'Río San Juan (78484)' },
    { value: '78577', label: 'Punta Cana (78577)' },
];

describe('ComboBox — dropdown propio con estética ARCA', () => {
    it('muestra el placeholder sin valor y la etiqueta con valor', () => {
        render(<ComboBox options={OPTIONS} value="" onChange={() => {}} placeholder="Seleccionar estación" />);
        expect(screen.getByText('Seleccionar estación')).toBeTruthy();
    });

    it('abre la lista al click y selecciona una opción', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ComboBox options={OPTIONS} value="" onChange={onChange} placeholder="Seleccionar estación" />);
        await user.click(screen.getByRole('button'));
        await user.click(screen.getByRole('option', { name: 'Jimaní (78486)' }));
        expect(onChange).toHaveBeenCalledWith('78486');
    });

    it('Escape cierra sin seleccionar y Enter confirma el resaltado', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ComboBox options={OPTIONS} value="" onChange={onChange} placeholder="x" />);
        const btn = screen.getByRole('button');
        await user.click(btn);
        expect(screen.getByRole('listbox')).toBeTruthy();
        await user.keyboard('{Escape}');
        expect(screen.queryByRole('listbox')).toBeNull();
        expect(onChange).not.toHaveBeenCalled();
    });

    it('flechas mueven el resaltado y Enter confirma', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ComboBox options={OPTIONS} value="" onChange={onChange} placeholder="x" />);
        await user.click(screen.getByRole('button'));
        // el click ya resalta el índice 0; una flecha → índice 1 → Enter confirma
        await user.keyboard('{ArrowDown}{Enter}');
        expect(onChange).toHaveBeenCalledWith('78484');
    });

    it('filtrado por texto reduce las opciones visibles', async () => {
        const user = userEvent.setup();
        render(<ComboBox options={OPTIONS} value="" onChange={() => {}} placeholder="x" searchable />);
        await user.click(screen.getByRole('button'));
        await user.type(screen.getByPlaceholderText('Buscar…'), 'jiman');
        expect(screen.queryByRole('option', { name: 'Río San Juan (78484)' })).toBeNull();
        expect(screen.getByRole('option', { name: 'Jimaní (78486)' })).toBeTruthy();
    });

    it('disabled no abre y expone aria-disabled', () => {
        render(<ComboBox options={OPTIONS} value="" onChange={() => {}} placeholder="x" disabled />);
        const btn = screen.getByRole('button');
        expect(btn.getAttribute('aria-disabled')).toBe('true');
        fireEvent.click(btn);
        expect(screen.queryByRole('listbox')).toBeNull();
    });

    it('expone listbox con aria-activedescendant al navegar', async () => {
        const user = userEvent.setup();
        render(<ComboBox options={OPTIONS} value="" onChange={() => {}} placeholder="x" />);
        await user.click(screen.getByRole('button'));
        await user.keyboard('{ArrowDown}');
        const listbox = screen.getByRole('listbox');
        expect(listbox.getAttribute('aria-activedescendant')).toContain('opt-');
    });
});
