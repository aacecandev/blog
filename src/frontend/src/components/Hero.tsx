import "./Hero.css";
import profilePicture from "../assets/profile-picture.jpeg";

export default function Hero() {
  return (
    <section className="hero">
      <div className="hero-content">
        <div className="hero-text">
          <h1>I'm Alejandro, a SRE(DevOps/MLOps) engineer building things</h1>
          <p>This is where I share my thoughts on technology and software engineering.</p>
        </div>
        <img src={profilePicture} alt="Alejandro" className="hero-avatar" />
      </div>
    </section>
  );
}
