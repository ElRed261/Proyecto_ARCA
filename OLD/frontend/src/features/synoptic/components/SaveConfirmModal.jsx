import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';

/**
 * SaveConfirmModal — guardado honesto.
 *
 * Antes de guardar, muestra qué horas quedaron a medio llenar para que el
 * observador decida con información (antes se guardaba a ciegas y las horas
 * no visitadas quedaban sin resultados calculados).
 */
const SaveConfirmModal = ({ open, incomplete, emptyCount, onConfirm, onCancel }) => {
    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
            role="dialog"
            aria-modal="true"
            aria-label="Confirmar guardado con horas incompletas"
        >
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
                <div className="flex items-center gap-2.5 mb-3">
                    <span className="w-9 h-9 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center flex-none">
                        <AlertTriangle size={18} />
                    </span>
                    <h3 className="text-lg font-bold text-slate-900">Hay horas sin completar</h3>
                </div>
                <p className="text-sm text-slate-600 mb-3">
                    Estas horas tienen datos parciales y se guardarán tal cual. Las horas
                    totalmente vacías ({emptyCount}) se guardan vacías.
                </p>
                <ul className="max-h-48 overflow-auto rounded-lg border border-slate-200 divide-y divide-slate-100 mb-4">
                    {incomplete.map(({ hora, done, total }) => (
                        <li key={hora} className="flex items-center justify-between px-3 py-2 text-sm">
                            <span className="font-bold text-slate-700">{hora}</span>
                            <span className="text-slate-500">
                                {done}/{total} campos
                            </span>
                        </li>
                    ))}
                </ul>
                <div className="flex gap-2 justify-end">
                    <button
                        type="button"
                        onClick={onCancel}
                        className="px-4 py-2 rounded-lg text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 cursor-pointer min-h-[44px]"
                    >
                        Revisar
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        className="px-4 py-2 rounded-lg text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 cursor-pointer min-h-[44px] flex items-center gap-1.5"
                    >
                        <CheckCircle size={16} />
                        Guardar igual
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SaveConfirmModal;
