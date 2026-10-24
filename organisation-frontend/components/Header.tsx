type HeaderProps = {
  onMenuClick?: () => void;
};

export default function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="fixed top-0 left-0 lg:left-64 right-0 h-16 bg-surface z-40 flex items-center justify-between px-space-md sm:px-space-xl gap-space-md sm:gap-space-lg">
      <button
        aria-label="Open menu"
        className="lg:hidden p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant"
        onClick={onMenuClick}
        type="button"
      >
        <span className="material-symbols-outlined text-[22px]">menu</span>
      </button>
      <div className="flex-1 max-w-xl">
        <div className="relative flex items-center">
          <span className="material-symbols-outlined absolute left-3 text-outline text-[20px]">
            search
          </span>
          <input
            className="w-full h-10 pl-10 pr-4 bg-surface-container-lowest rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary "
            placeholder="Search claims, employees, pharmacies, invoices..."
            type="text"
          />
        </div>
      </div>
      <div className="flex items-center gap-space-md sm:gap-space-lg">
        <button
          aria-label="Notifications"
          className="relative p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant transition-colors"
          type="button"
        >
          <span className="material-symbols-outlined text-[22px]">notifications</span>
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-error ring-2 ring-surface"></span>
        </button>
        <div className="h-8 w-px bg-surface-container-high"></div>
        <div className="flex items-center gap-space-sm">
          <img
            alt="Profile"
            className="w-8 h-8 rounded-full object-cover ring-1 ring-primary/20"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuD2hHXaiA_gidjqDFb7zu5DvnGrQUCXD3znBHNchOO5ITarjO4h2nhZ4pQJzswvsHmeMw7amI1b7w0ZXSr2edFslCS9004uIz_tfxbYh-DpHqTq6FMuNilK_xUPOkp3rxklX1JzwtFlCyE8UXoSBi0iMfondOHq9yv1KV9Lc7g9aJXDmJ7LgUVDJDkZG-adpLQS68riuJeFkwpfcM4XOhB-uV7RRY-1_vTE5XHbRX7QlwHNQomi21Or"
          />
          <div className="hidden sm:flex flex-col text-left">
            <span className="font-label-md text-label-md text-on-surface font-semibold">
              Selamawit Tadesse
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Lead People &amp; Benefits
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}