export default function DevBeezLogo() {
  return <span className="devbeez-logo">
    <img src={`${import.meta.env.BASE_URL}images/devbeez-logo.png`} alt="DevBeez — The FullStack Hive" width="1080" height="1080" />
  </span>;
}
