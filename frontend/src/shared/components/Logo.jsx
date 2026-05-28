import React from 'react';

const Logo = ({ variant = 'medium', className = '' }) => {
    // Colors
    const primaryColor = '#2563EB'; // blue-600
    const secondaryColor = '#1F2937'; // gray-800
    const accentColor = '#60A5FA'; // blue-400

    // Icon Path (Abstract Hexagon/Shield)
    const iconPath = (
        <g>
            <path d="M12 2L2 7L12 12L22 7L12 2Z" fill={primaryColor} />
            <path d="M2 17L12 22L22 17" stroke={primaryColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12L12 17L22 12" stroke={accentColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 22V12" stroke={primaryColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </g>
    );

    const iconElement = (
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
            {iconPath}
        </svg>
    );

    if (variant === 'simple') {
        return iconElement;
    }

    return (
        <div className={`flex items-center gap-3 ${className}`}>
            {iconElement}
            <div className="flex flex-col">
                <span className="text-xl font-bold tracking-tight" style={{ color: secondaryColor }}>
                    {variant === 'full' ? 'Proyecto ARCA' : 'ARCA'}
                </span>
                {variant === 'full' && (
                    <span className="text-[0.65rem] font-medium tracking-wider uppercase text-gray-500 leading-none">
                        Enterprise ERP
                    </span>
                )}
            </div>
        </div>
    );
};

export default Logo;
