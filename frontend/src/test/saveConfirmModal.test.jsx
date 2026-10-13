import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SaveConfirmModal from '../features/synoptic/components/SaveConfirmModal';

const PROPS = {
    open: true,
    incomplete: [
        { hora: '06Z', done: 5, total: 21 },
        { hora: '12Z', done: 12, total: 21 },
    ],
    emptyCount: 6,
    onConfirm: () => {},
    onCancel: () => {},
};

describe('SaveConfirmModal — guardado honesto', () => {
    it('no renderiza nada si está cerrado', () => {
        render(<SaveConfirmModal {...PROPS} open={false} onConfirm={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('lista las horas incompletas con su avance', () => {
        render(<SaveConfirmModal {...PROPS} onConfirm={vi.fn()} onCancel={vi.fn()} />);
        expect(screen.getByRole('dialog')).toBeTruthy();
        expect(screen.getByText('06Z')).toBeTruthy();
        expect(screen.getByText('5/21 campos')).toBeTruthy();
        expect(screen.getByText(/totalmente vacías \(6\)/)).toBeTruthy();
    });

    it('Guardar igual confirma y Revisar cancela', () => {
        const onConfirm = vi.fn();
        const onCancel = vi.fn();
        render(<SaveConfirmModal {...PROPS} onConfirm={onConfirm} onCancel={onCancel} />);
        fireEvent.click(screen.getByRole('button', { name: /guardar igual/i }));
        expect(onConfirm).toHaveBeenCalledTimes(1);
        fireEvent.click(screen.getByRole('button', { name: /revisar/i }));
        expect(onCancel).toHaveBeenCalledTimes(1);
    });
});
