# main.py

from prompt import Prompt
import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Calculates the number of tokens in a given string using OpenAI's tokenizer.

    :param text: The input string to tokenize.
    :param model: The model name (default is "gpt-4o").
                  Other options: "gpt-4", "gpt-3.5-turbo", etc.
    :return: The number of tokens in the input text.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding(
            "cl100k_base"
        )  # Fallback for unsupported models

    token_count = len(encoding.encode(text))
    return token_count


# Example dynamic data
episode_meta_data = {
    "episode_title": "Climate and Space Adventures",
    "episode_number": "1st",
    "week_date": "February 5, 2025",
    "list_of_main_topics": "Space Mining, Deep Space Propulsion, Advanced AI Technologies",
}

episode_content = """
### Space Technologies

#### Space Mining
- Asteroid mining is being explored as a way to extract rare minerals like platinum and gold.
- Companies like AstroForge and Planetary Resources are working on spacecraft capable of mining near-Earth asteroids.
- NASA’s OSIRIS-REx mission has already collected samples from the asteroid Bennu, showcasing proof-of-concept for resource extraction.

#### Orbital Manufacturing
- The microgravity environment in space allows for the production of materials with **unmatched purity and strength**.
- Companies like Varda Space and Redwire are developing **3D printing factories** in orbit to manufacture high-performance semiconductors and bioengineered tissues.
- Space-based manufacturing could revolutionize industries on Earth by creating **superior alloys and fiber optics**.

### Deep Space Propulsion

#### Nuclear Thermal & Electric Propulsion
- NASA and DARPA are developing **Nuclear Thermal Propulsion (NTP)**, which could cut Mars travel time by half.
- Electric propulsion, like **ion thrusters**, is used in deep space missions such as NASA's **DART mission** and the **Psyche mission to a metal-rich asteroid**.
- Advanced plasma-based propulsion systems, such as **VASIMR (Variable Specific Impulse Magnetoplasma Rocket)**, could enable high-speed interstellar travel.

#### Solar Sails & Laser Propulsion
- The **Breakthrough Starshot project** is exploring **light sail technology** to propel tiny probes to Proxima Centauri using powerful ground-based lasers.
- Japan’s **IKAROS mission** successfully demonstrated **solar sail propulsion**, using sunlight pressure for continuous acceleration.
- Future applications include **interstellar travel** and **low-energy space maneuvers**.

### Advanced AI Technologies

#### Artificial General Intelligence (AGI)
- OpenAI, DeepMind, and Anthropic are leading the race to develop AGI, aiming for AI systems that **match or exceed human-level intelligence** across all cognitive tasks.
- **DeepMind’s Gato** and OpenAI’s **Q* (Q-star)** are considered early attempts at generalized AI models.
- A major challenge is **alignment**—ensuring AGI operates safely within human values and doesn’t become uncontrollable.

#### Neuromorphic Computing & Brain-Inspired AI
- Neuromorphic chips, such as Intel’s **Loihi 2** and IBM’s **TrueNorth**, are designed to mimic the human brain’s neural architecture.
- These AI systems process data **more efficiently than traditional deep learning**, using **spiking neural networks (SNNs)**.
- DARPA and various research institutions are exploring **AI models that self-learn in real-time**, much like the human brain.

"""

# Dynamically format the prompt with episode metadata & content
formatted_prompt = Prompt.format(
    episode_title=episode_meta_data["episode_title"],
    episode_number=episode_meta_data["episode_number"],
    week_date=episode_meta_data["week_date"],
    list_of_main_topics=episode_meta_data["list_of_main_topics"],
    episode_content=episode_content,  # Injecting only once!
)

# Print or send the formatted prompt to the LLM
# Example usage:
# sample_text = "This is a sample text to check token count."
tokens = count_tokens(formatted_prompt)
print(f"Token count: {tokens}")


print(formatted_prompt)
