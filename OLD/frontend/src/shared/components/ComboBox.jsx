import React, { useState, useRef, useEffect, useId } from 'react';
import { ChevronDown, Check } from 'lucide-react';

/**
 * ComboBox — dropdown propio con la estética ARCA.
 *
 * Reemplaza los <select> nativos (distintos en cada OS/browser) por un
 * botón + listbox con: chevron propio, resaltado por teclado (↑↓/Enter/Escape),
 * filtro opcional para listas largas y roles ARIA de listbox.
 *
 * Props:
 *  - options: [{ value, label }]
 *  - value: value seleccionado ('' = ninguno)
 *  - onChange(value)
 *  - placeholder, disabled, searchable, className, ariaLabel, id
 */
const ComboBox = ({
    options = [],
    value = '',
    onChange,
    placeholder = 'Seleccionar…',
    disabled = false,
    searchable = false,
    className = '',
    ariaLabel,
    id,
}) => {
    const [open, setOpen] = useState(false);
    const [highlight, setHighlight] = useState(-1);
    const [filter, setFilter] = useState('');
    const rootRef = useRef(null);
    const listRef = useRef(null);
    const uid = useId().replace(/:/g, '');
    const selected = options.find((o) => String(o.value) === String(value));

    const visible = filter
        ? options.filter((o) => o.label.toLowerCase().includes(filter.toLowerCase()))
        : options;

    // foco único al abrir (teclado inmediato) — sin robar foco en cada render
    useEffect(() => {
        if (open && !searchable && listRef.current) {
            listRef.current.focus({ preventScroll: true });
        }
    }, [open, searchable]);

    // cerrar al click fuera + Escape global
    useEffect(() => {
        if (!open) return;
        const onDocClick = (e) => {
            if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
        };
        const onKey = (e) => {
            if (e.key === 'Escape') setOpen(false);
        };
        document.addEventListener('mousedown', onDocClick);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDocClick);
            document.removeEventListener('keydown', onKey);
        };
    }, [open ]);

    const choose = (v) => {
        setOpen(false);
        setFilter('');
        setHighlight(-1);
        onChange(v);
    };

    const onButtonKey = (e) => {
        if (disabled) return;
        if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
            e.preventDefault();
            if (!open) {
                setOpen(true);
                setHighlight(0);
            } else {
                onListKey(e);
            }
        }
    };

    const onListKey = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setHighlight((h) => Math.min(h + 1, visible.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setHighlight((h) => Math.max(h - 1, 0));
        } else if (e.key === 'Enter' && highlight >= 0 && visible[highlight]) {
            e.preventDefault();
            choose(visible[highlight].value);
        }
    };

    return (
        <div ref={rootRef} className={`relative ${className}`} id={id}>
            <button
                type="button"
                role="button"
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-disabled={disabled || undefined}
                aria-label={ariaLabel || placeholder}
                disabled={disabled}
                onClick={() => {
                    if (disabled) return;
                    setOpen((o) => !o);
                    setHighlight(0);
                }}
                onKeyDown={onButtonKey}
                className={`w-full flex items-center justify-between gap-2 text-sm px-3 py-2 rounded-lg border bg-white transition-all duration-150 min-h-[40px] ${
                    disabled
                        ? 'bg-gray-200 text-gray-400 border-gray-200 cursor-not-allowed opacity-75'
                        : 'border-slate-300 text-slate-800 hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 cursor-pointer shadow-sm'
                } ${!selected ? 'text-slate-400' : ''}`}
            >
                <span className="truncate">{selected ? selected.label : placeholder}</span>
                <ChevronDown
                    className={`w-4 h-4 flex-none transition-transform duration-150 ${open ? 'rotate-180' : ''} ${
                        disabled ? 'text-gray-300' : 'text-slate-500'
                    }`}
                />
            </button>

            {open && !disabled && (
                <div className="absolute z-50 mt-1 w-full min-w-full">
                    <div
                        role="listbox"
                        aria-activedescendant={highlight >= 0 && visible[highlight] ? `opt-${uid}-${highlight}` : undefined}
                        tabIndex={-1}
                        onKeyDown={onListKey}
                        className="max-h-60 overflow-auto rounded-lg border border-slate-200 bg-white shadow-xl py-1 outline-none"
                        ref={listRef}
                    >
                        {searchable && (
                            <div className="sticky top-0 bg-white px-2 pt-1 pb-1 border-b border-slate-100">
                                <input
                                    type="text"
                                    placeholder="Buscar…"
                                    value={filter}
                                    onChange={(e) => {
                                        setFilter(e.target.value);
                                        setHighlight(0);
                                    }}
                                    onKeyDown={onListKey}
                                    className="w-full text-sm px-2 py-1.5 rounded-md border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500"
                                />
                            </div>
                        )}
                        {visible.length === 0 && (
                            <div className="px-3 py-2 text-sm text-slate-400">Sin resultados</div>
                        )}
                        {visible.map((o, i) => {
                            const active = String(o.value) === String(value);
                            const hot = i === highlight;
                            return (
                                <div
                                    key={o.value}
                                    id={`opt-${uid}-${i}`}
                                    role="option"
                                    aria-selected={active}
                                    onMouseEnter={() => setHighlight(i)}
                                    onClick={() => choose(o.value)}
                                    className={`flex items-center justify-between gap-2 px-3 py-2 text-sm cursor-pointer transition-colors ${
                                        hot ? 'bg-blue-50 text-slate-900' : 'text-slate-700'
                                    }`}
                                >
                                    <span className="truncate">{o.label}</span>
                                    {active && <Check className="w-4 h-4 text-blue-600 flex-none" />}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ComboBox;
