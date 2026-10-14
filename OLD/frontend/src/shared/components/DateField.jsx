import React, { useState } from 'react';
import { formatIsoToDisplay, parseDisplayToIso, maskDateInput } from '../utils/dateMask';
import { CalendarDays } from 'lucide-react';

/**
 * DateField — fecha DD/MM/YYYY con máscara de tipeo, SIN el date-picker
 * nativo del OS (ese control es lo que más "oía a browser" en las planillas).
 *
 * Contrato: `value` es ISO (YYYY-MM-DD, lo que el backend espera);
 * `onChange(iso|'')` solo se dispara con fechas calendario REALES.
 */
const DateField = ({
    value,
    onChange,
    className = '',
    disabled = false,
    id,
    ariaLabel = 'Fecha (DD/MM/AAAA)',
}) => {
    const [text, setText] = useState(() => formatIsoToDisplay(value));
    const [lastValue, setLastValue] = useState(value);

    // el padre manda (navegación de día, carga): resincronizar durante el render
    if (value !== lastValue) {
        setLastValue(value);
        setText(formatIsoToDisplay(value));
    }

    const invalid = text.length === 10 && !parseDisplayToIso(text).valid;

    const commit = (next) => {
        setText(next);
        if (next.length === 10) {
            const { iso, valid } = parseDisplayToIso(next);
            if (valid) {
                onChange(iso);
            }
            return;
        }
        if (next.length === 0) onChange('');
    };

    return (
        <div className="relative">
            <input
                type="text"
                inputMode="numeric"
                id={id}
                aria-label={ariaLabel}
                aria-invalid={invalid || undefined}
                title="Fecha en formato DD/MM/AAAA"
                placeholder="DD/MM/AAAA"
                autoComplete="off"
                disabled={disabled}
                value={text}
                onChange={(e) => commit(maskDateInput(e.target.value))}
                onBlur={() => {
                    // al salir: fecha incompleta/inválida revierte al último valor válido
                    if (
                        (text.length > 0 && text.length < 10) ||
                        (text.length === 10 && !parseDisplayToIso(text).valid)
                    ) {
                        setText(formatIsoToDisplay(value));
                    }
                }}
                className={`${className} ${invalid ? 'border-red-400 ring-1 ring-red-300' : ''}`}
            />
            <CalendarDays
                className="w-4 h-4 text-slate-400 pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2"
                aria-hidden="true"
            />
        </div>
    );
};

export default DateField;
