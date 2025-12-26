'use client';

export const HowItWorksStep = ({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) => (
    <div className="relative flex flex-col items-center text-center">
        <div className="absolute top-8 left-1/2 w-px h-full border-l-2 border-dashed border-border -z-10 hidden md:block"></div>
        <div className="relative bg-background p-2 rounded-full z-10">
            <div className="bg-primary/10 text-primary p-5 rounded-full ring-4 ring-background">
                {icon}
            </div>
        </div>
        <h3 className="mt-6 text-xl font-bold text-text-light">{title}</h3>
        <p className="mt-2 text-text-muted max-w-xs">{description}</p>
    </div>
);
